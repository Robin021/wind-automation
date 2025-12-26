import sys
sys.path.append('/app')
from backend.core.database import SessionLocal
from backend.api.v1.payments import PaymentOrder
from backend.services.wechat_pay import query_order
from backend.models.user import User
from backend.services.subscription_service import grant_or_extend_subscription
from datetime import datetime
import json

def run():
    db = SessionLocal()
    try:
        oid = 'WX20251226131402DB292AEF'
        print(f'Checking {oid}...')
        order = db.query(PaymentOrder).filter(PaymentOrder.out_trade_no == oid).first()
        if not order:
            print('Order not found')
        else:
            print(f'Order user: {order.user_id}, Status: {order.status}')
            if order.status == 'paid':
                 print('Already paid')
            else:
                 suc, data = query_order(oid)
                 if suc and data and data.get('trade_state') == 'SUCCESS':
                      print('WeChat says SUCCESS. Updating...')
                      order.status = 'paid'
                      order.paid_at = datetime.utcnow()
                      order.raw_notify = json.dumps(data)
                      user = db.query(User).filter(User.id == order.user_id).first()
                      if user:
                          grant_or_extend_subscription(db, user, order.vip_level, order.duration_months)
                      db.commit()
                      print('Updated to PAID.')
                 else:
                      print(f'WeChat status: {data.get("trade_state") if data else "Error"}')
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    run()
