import os ;\
import site ;\
import sys ;\
os.system('mkdir -p ' + site.getusersitepackages()) ;\
os.system('ln -sf "/Applications/Wind API.app/Contents/python/WindPy.py"' + ' ' + site.getusersitepackages()) ;\
os.system('ln -sf "/Applications/Wind API.app/Contents/python/WindPy.py"' + ' ' + site.getsitepackages()[0]) ;\
os.system('rm -rf ~/.Wind') ;\
os.system('ln -sf ~/Library/Containers/com.wind.mac.api/Data/.Wind ~/.Wind') ;\
print("Current Python Version: " + sys.version) ;\
print("Current Python Env: " + sys.executable) ;\
print("WindPy installed at: " + site.getusersitepackages()) ;\
print("WindPy installed at: " + site.getsitepackages()[0])
