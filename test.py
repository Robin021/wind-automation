from WindPy import *

w = w.start()
print(w)

print(w.isconnected())

 #test WSS function
ret = w.wss("000001.SZ", "sec_name","")
print(ret)