"""
微信支付 V3：签名下单 + 平台证书验签 + 回调解密

说明：
- 这里实现“最小可用”的 V3 核心能力，方便直接挂到 API。
- 平台证书支持两种方式：
  1) 配置本地平台证书 PEM（最稳）
  2) 通过 /v3/certificates 自动拉取（需要先能签名请求）
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _utc_timestamp() -> str:
    # Use epoch seconds to avoid naive datetime timezone shifts
    return str(int(time.time()))


def _nonce_str() -> str:
    return secrets.token_hex(16)


def _to_bytes(s: str) -> bytes:
    return s.encode("utf-8")


def _b64decode(s: str) -> bytes:
    return base64.b64decode(s)


def _load_private_key_pem(path: str) -> rsa.RSAPrivateKey:
    if not os.path.exists(path):
        raise FileNotFoundError(f"微信商户私钥文件不存在: {path}")
    with open(path, "rb") as f:
        data = f.read()
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("商户私钥必须是 RSA 私钥（PEM）")
    return key


def _load_platform_public_key(path: str) -> rsa.RSAPublicKey:
    if not os.path.exists(path):
        raise FileNotFoundError(f"微信平台证书/公钥文件不存在: {path}")
    with open(path, "rb") as f:
        data = f.read()
    try:
        cert = x509.load_pem_x509_certificate(data)
        pub = cert.public_key()
    except Exception:
        pub = serialization.load_pem_public_key(data)
    if not isinstance(pub, rsa.RSAPublicKey):
        raise ValueError("平台证书/公钥必须是 RSA 公钥（PEM）")
    return pub


def _rsa_sign(private_key: rsa.RSAPrivateKey, message: str) -> str:
    signature = private_key.sign(
        _to_bytes(message),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _rsa_verify(public_key: rsa.RSAPublicKey, message: str, signature_b64: str) -> bool:
    try:
        public_key.verify(
            _b64decode(signature_b64),
            _to_bytes(message),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def _build_signature_message(method: str, path_with_query: str, timestamp: str, nonce: str, body: str) -> str:
    # 按微信支付 V3 规范拼接：HTTPMethod\nURL\nTimestamp\nNonce\nBody\n
    return f"{method.upper()}\n{path_with_query}\n{timestamp}\n{nonce}\n{body}\n"


def decrypt_wechat_resource(api_v3_key: str, associated_data: str, nonce: str, ciphertext: str) -> Dict[str, Any]:
    key_bytes = _to_bytes(api_v3_key)
    if len(key_bytes) != 32:
        raise ValueError("WECHAT_PAY_API_V3_KEY 必须为 32 字节字符串")
    aesgcm = AESGCM(key_bytes)
    # 微信 ciphertext = base64(密文 + 16字节tag)
    ct = _b64decode(ciphertext)
    pt = aesgcm.decrypt(_to_bytes(nonce), ct, _to_bytes(associated_data))
    return json.loads(pt.decode("utf-8"))


@dataclass
class WechatPayConfig:
    mchid: str
    merchant_serial_no: str
    merchant_private_key_path: str
    api_v3_key: str
    notify_url: str

    # 各 appid（公众号/小程序）
    appid_mp: Optional[str] = None
    appid_mini: Optional[str] = None

    # 微信支付 API 基础域名
    base_url: str = "https://api.mch.weixin.qq.com"

    # 平台证书（可选：推荐配置本地 PEM）
    platform_cert_path: Optional[str] = None
    platform_serial_no: Optional[str] = None


class WechatPayV3Client:
    def __init__(self, cfg: WechatPayConfig):
        self.cfg = cfg
        self._merchant_key = _load_private_key_pem(cfg.merchant_private_key_path)

        self._platform_public_key: Optional[rsa.RSAPublicKey] = None
        if cfg.platform_cert_path:
            self._platform_public_key = _load_platform_public_key(cfg.platform_cert_path)

    def _auth_header(self, method: str, url: str, body: str) -> str:
        parsed = urlparse(url)
        path_with_query = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        timestamp = _utc_timestamp()
        nonce = _nonce_str()
        message = _build_signature_message(method, path_with_query, timestamp, nonce, body)
        signature = _rsa_sign(self._merchant_key, message)
        return (
            "WECHATPAY2-SHA256-RSA2048 "
            f'mchid="{self.cfg.mchid}",'
            f'nonce_str="{nonce}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self.cfg.merchant_serial_no}",'
            f'signature="{signature}"'
        )

    async def request(self, method: str, path: str, json_body: Optional[dict] = None) -> dict:
        url = self.cfg.base_url.rstrip("/") + path
        body = json.dumps(json_body, ensure_ascii=False, separators=(",", ":")) if json_body else ""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self._auth_header(method, url, body),
            "User-Agent": "wind-automation/1.0",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, headers=headers, content=body or None)
            if resp.status_code >= 400:
                raise RuntimeError(f"微信支付请求失败: {resp.status_code} {resp.text}")
            return resp.json()

    async def create_native(self, appid: str, description: str, out_trade_no: str, total_fen: int) -> Tuple[str, dict]:
        payload = {
            "appid": appid,
            "mchid": self.cfg.mchid,
            "description": description,
            "out_trade_no": out_trade_no,
            "notify_url": self.cfg.notify_url,
            "amount": {"total": total_fen, "currency": "CNY"},
        }
        data = await self.request("POST", "/v3/pay/transactions/native", payload)
        return data.get("code_url"), data

    async def create_h5(self, appid: str, description: str, out_trade_no: str, total_fen: int, client_ip: str) -> Tuple[str, dict]:
        payload = {
            "appid": appid,
            "mchid": self.cfg.mchid,
            "description": description,
            "out_trade_no": out_trade_no,
            "notify_url": self.cfg.notify_url,
            "amount": {"total": total_fen, "currency": "CNY"},
            "scene_info": {
                "payer_client_ip": client_ip,
                "h5_info": {"type": "Wap"},
            },
        }
        data = await self.request("POST", "/v3/pay/transactions/h5", payload)
        return data.get("h5_url"), data

    async def create_jsapi(self, appid: str, description: str, out_trade_no: str, total_fen: int, openid: str) -> Tuple[str, dict]:
        payload = {
            "appid": appid,
            "mchid": self.cfg.mchid,
            "description": description,
            "out_trade_no": out_trade_no,
            "notify_url": self.cfg.notify_url,
            "amount": {"total": total_fen, "currency": "CNY"},
            "payer": {"openid": openid},
        }
        data = await self.request("POST", "/v3/pay/transactions/jsapi", payload)
        return data.get("prepay_id"), data

    def verify_notify_signature(self, headers: Dict[str, str], body: str) -> bool:
        """
        验证回调签名。需要平台证书（推荐配置本地 platform_cert_path）。
        微信头：
        - Wechatpay-Timestamp
        - Wechatpay-Nonce
        - Wechatpay-Signature
        - Wechatpay-Serial
        """
        if not self._platform_public_key:
            raise RuntimeError("未配置 WECHAT_PAY_PLATFORM_CERT_PATH，无法验签微信回调")

        ts = headers.get("wechatpay-timestamp") or headers.get("Wechatpay-Timestamp")
        nonce = headers.get("wechatpay-nonce") or headers.get("Wechatpay-Nonce")
        sig = headers.get("wechatpay-signature") or headers.get("Wechatpay-Signature")
        serial = headers.get("wechatpay-serial") or headers.get("Wechatpay-Serial")
        if not ts or not nonce or not sig or not serial:
            return False

        # 可选：校验 serial 是否匹配配置，避免用错证书
        if self.cfg.platform_serial_no and serial != self.cfg.platform_serial_no:
            return False

        message = f"{ts}\n{nonce}\n{body}\n"
        return _rsa_verify(self._platform_public_key, message, sig)



