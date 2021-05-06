

from inspect import getsource



from collections import OrderedDict




class Z(object):
    def __init__(self):
        
        self.defin()
        
        
        
    
    
    
    def defin(self):
        print ("woo hoo")
        a = 99
        c = 88
        b = 0
        
        



z = Z()
mem = OrderedDict()
exec("\n".join(line.lstrip() for line in getsource(Z.defin).split("\n")[1:]), globals(), mem)

print(mem)
