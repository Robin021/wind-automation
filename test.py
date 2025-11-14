from WindPy import w

w.start()
print(w.isconnected())  # True 表示连上了 Wind 服务
ret = w.wss("000001.SZ", "sec_name", "")
print(ret)
