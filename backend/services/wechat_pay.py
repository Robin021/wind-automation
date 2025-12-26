"""
微信支付 V3 服务
封装微信支付 Native/H5/JSAPI 下单接口
"""
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from wechatpayv3 import WeChatPay, WeChatPayType

from backend.core.config import settings

logger = logging.getLogger(__name__)

# 全局微信支付实例（延迟初始化）
_wxpay_instance: Optional[WeChatPay] = None


def _load_private_key() -> str:
    """加载商户私钥"""
    key_path = settings.WECHAT_PAY_MERCHANT_PRIVATE_KEY_PATH
    if not key_path:
        raise ValueError("WECHAT_PAY_MERCHANT_PRIVATE_KEY_PATH 未配置")
    
    # 支持相对路径和绝对路径
    path = Path(key_path)
    if not path.is_absolute():
        path = Path("/app") / key_path  # Docker 容器内路径
        if not path.exists():
            path = Path(key_path)  # 本地开发路径
    
    if not path.exists():
        raise FileNotFoundError(f"商户私钥文件不存在: {key_path}")
    
    return path.read_text()


def get_wxpay() -> WeChatPay:
    """获取微信支付实例（单例）"""
    global _wxpay_instance
    
    if _wxpay_instance is not None:
        return _wxpay_instance
    
    # 验证必要配置
    if not settings.WECHAT_PAY_MCHID:
        raise ValueError("WECHAT_PAY_MCHID 未配置")
    if not settings.WECHAT_PAY_API_V3_KEY:
        raise ValueError("WECHAT_PAY_API_V3_KEY 未配置")
    
    private_key = _load_private_key()
    
    _wxpay_instance = WeChatPay(
        wechatpay_type=WeChatPayType.NATIVE,
        mchid=settings.WECHAT_PAY_MCHID,
        private_key=private_key,
        cert_serial_no=settings.WECHAT_PAY_MERCHANT_SERIAL_NO,
        apiv3_key=settings.WECHAT_PAY_API_V3_KEY,
        appid=settings.WECHAT_PAY_APPID_MP,  # 默认使用公众号 AppID
        notify_url=settings.WECHAT_PAY_NOTIFY_URL,
        logger=logger,
    )
    
    return _wxpay_instance


def create_native_order(
    out_trade_no: str,
    description: str,
    amount_fen: int,
) -> Tuple[bool, str, Optional[str]]:
    """
    创建 Native 支付订单（扫码支付）
    
    返回: (success, message, code_url)
    """
    wxpay = get_wxpay()
    
    try:
        code, response = wxpay.pay(
            description=description,
            out_trade_no=out_trade_no,
            amount={"total": amount_fen, "currency": "CNY"},
            pay_type=WeChatPayType.NATIVE,
        )
        
        logger.info(f"Native 下单响应: code={code}, response={response}")
        
        if code == 200:
            data = json.loads(response) if isinstance(response, str) else response
            code_url = data.get("code_url")
            return True, "下单成功", code_url
        else:
            error_msg = response if isinstance(response, str) else json.dumps(response)
            logger.error(f"Native 下单失败: {error_msg}")
            return False, f"下单失败: {error_msg}", None
            
    except Exception as e:
        logger.exception("Native 下单异常")
        return False, f"下单异常: {str(e)}", None


def create_h5_order(
    out_trade_no: str,
    description: str,
    amount_fen: int,
    payer_ip: str,
) -> Tuple[bool, str, Optional[str]]:
    """
    创建 H5 支付订单（手机浏览器支付）
    
    返回: (success, message, h5_url)
    """
    wxpay = get_wxpay()
    
    try:
        code, response = wxpay.pay(
            description=description,
            out_trade_no=out_trade_no,
            amount={"total": amount_fen, "currency": "CNY"},
            pay_type=WeChatPayType.H5,
            scene_info={
                "payer_client_ip": payer_ip,
                "h5_info": {"type": "Wap"}
            },
        )
        
        logger.info(f"H5 下单响应: code={code}, response={response}")
        
        if code == 200:
            data = json.loads(response) if isinstance(response, str) else response
            h5_url = data.get("h5_url")
            return True, "下单成功", h5_url
        else:
            error_msg = response if isinstance(response, str) else json.dumps(response)
            logger.error(f"H5 下单失败: {error_msg}")
            return False, f"下单失败: {error_msg}", None
            
    except Exception as e:
        logger.exception("H5 下单异常")
        return False, f"下单异常: {str(e)}", None


def create_jsapi_order(
    out_trade_no: str,
    description: str,
    amount_fen: int,
    openid: str,
) -> Tuple[bool, str, Optional[str]]:
    """
    创建 JSAPI 支付订单（公众号/小程序内支付）
    
    返回: (success, message, prepay_id)
    """
    wxpay = get_wxpay()
    
    try:
        code, response = wxpay.pay(
            description=description,
            out_trade_no=out_trade_no,
            amount={"total": amount_fen, "currency": "CNY"},
            pay_type=WeChatPayType.JSAPI,
            payer={"openid": openid},
        )
        
        logger.info(f"JSAPI 下单响应: code={code}, response={response}")
        
        if code == 200:
            data = json.loads(response) if isinstance(response, str) else response
            prepay_id = data.get("prepay_id")
            return True, "下单成功", prepay_id
        else:
            error_msg = response if isinstance(response, str) else json.dumps(response)
            logger.error(f"JSAPI 下单失败: {error_msg}")
            return False, f"下单失败: {error_msg}", None
            
    except Exception as e:
        logger.exception("JSAPI 下单异常")
        return False, f"下单异常: {str(e)}", None


def verify_and_decrypt_callback(headers: dict, body: str) -> Tuple[bool, Optional[dict]]:
    """
    验证并解密微信支付回调
    
    返回: (success, decrypted_data)
    """
    wxpay = get_wxpay()
    
    try:
        result = wxpay.callback(headers=headers, body=body)
        if result:
            return True, result
        return False, None
    except Exception as e:
        logger.exception("回调验签/解密失败")
        return False, None


def query_order(out_trade_no: str) -> Tuple[bool, Optional[dict]]:
    """
    查询订单状态
    
    返回: (success, order_data)
    """
    wxpay = get_wxpay()
    
    try:
        code, response = wxpay.query(out_trade_no=out_trade_no)
        
        if code == 200:
            data = json.loads(response) if isinstance(response, str) else response
            return True, data
        else:
            return False, None
            
    except Exception as e:
        logger.exception("查询订单异常")
        return False, None
