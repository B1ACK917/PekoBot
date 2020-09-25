import datetime
import numpy as np

# a = {'美杜莎': [(1, 'aaa'), (2, 'bbb'), (3, 'ccc')]}
# np.save('./Resource/a.npy', a,allow_pickle=True)
b=np.load('./Resource/a.npy',allow_pickle=True).item()
print(b)
