#!/usr/bin/env python
import os
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
import tensorflow as tf
import numpy as np
from netCDF4 import Dataset

num_convf = convfilter
num_hiddf = hiddfilter
xdim = xxx
ydim = yyy
zdim = zzz
xdim2 = int(xdim/4)
ydim2 = int(ydim/4)
sample_size = SAMSIZ
test_size = TSTSIZ
tot_size = TOTSIZ

def init_weights(shape):
    return tf.Variable(tf.random.normal(shape, stddev=1))

def init_bias(shape):
    return tf.Variable(tf.random.uniform(shape, minval=-0.01, maxval=0.01))

# Input Data
inpv1 = np.zeros((test_size,zdim,ydim,xdim), dtype=np.float32)
inp1 = Dataset('/home/jhkim/data/samfile','r')
inpv1[:,0:3,:,:] = inp1.variables['sst'][sample_size:tot_size,:,:,:]
inpv1[:,3:6,:,:] = inp1.variables['t300'][sample_size:tot_size,:,:,:]

reinp1 = np.swapaxes(inpv1,1,3) # (tdim,zdim,ydim,xdim) -> (tdim,xdim,ydim,zdim)
teX = reinp1[:,:,:,:] 

with tf.device('/gpu:number_gpu'):
  # Define Dimension
  teX = teX.reshape(-1, xdim, ydim, zdim) 
  X = tf.compat.v1.placeholder(tf.float32, [None, xdim, ydim, zdim])
  
  w = init_weights([8, 4, zdim, num_convf])  
  b = init_bias([num_convf])
  w2 = init_weights([4, 2, num_convf, num_convf])
  b2 = init_bias([num_convf])
  w3 = init_weights([4, 2, num_convf, num_convf])
  b3 = init_bias([num_convf])
  w4 = init_weights([num_convf * xdim2 * ydim2, num_hiddf])
  b4 = init_bias([num_hiddf])
  w_o = init_weights([num_hiddf, 3])
  b_o = init_bias([3])
  
  # Drop out
  p_keep_conv = tf.compat.v1.placeholder(tf.float32)
  p_keep_hidden = tf.compat.v1.placeholder(tf.float32)
  
  # Model
  l1a = tf.tanh(tf.nn.conv2d(X, filters=w, strides=[1, 1, 1, 1], padding='SAME') + b)
  l1 = tf.nn.max_pool2d(input=l1a, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
  l1 = tf.nn.dropout(l1, rate=1 - (p_keep_conv))
  
  l2a = tf.tanh(tf.nn.conv2d(l1, filters=w2, strides=[1, 1, 1, 1], padding='SAME') + b2)
  l2 = tf.nn.max_pool2d(input=l2a, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
  l2 = tf.nn.dropout(l2, rate=1 - (p_keep_conv))
  
  l3a = tf.tanh(tf.nn.conv2d(l2, filters=w3, strides=[1, 1, 1, 1], padding='SAME') + b3)
  l3 = tf.reshape(l3a, [-1, w4.get_shape().as_list()[0]])
  l3 = tf.nn.dropout(l3, rate=1 - (p_keep_conv))
  
  l4 = tf.tanh(tf.matmul(l3, w4) + b4)
  l4 = tf.nn.dropout(l4, rate=1 - (p_keep_hidden))
  
  py_x = tf.matmul(l4, w_o) + b_o
  predict_op = tf.argmax(py_x,1)

saver = tf.compat.v1.train.Saver()
config = tf.compat.v1.ConfigProto()
config.gpu_options.allow_growth = True

# Launch the graph in a session
with tf.compat.v1.Session(config=config) as sess:
    saver.restore(sess,'home_directory/output/case/opfname/ENmember/model.ckpt')

    result = sess.run(predict_op, feed_dict={X: teX, p_keep_conv:1.0, 
                      p_keep_hidden:1.0})

    result.astype('float32').tofile('home_directory/output/case/opfname/ENmember/result.gdat')

ctl_EOF = open('home_directory/output/case/opfname/ENmember/result.ctl','w')
ctl_EOF.write('dset ^result.gdat\n')
ctl_EOF.write('undef -9.99e+08\n')
ctl_EOF.write('xdef   1  linear  0.   5\n')
ctl_EOF.write('ydef   1  linear -55.  5\n')
ctl_EOF.write('zdef   1  linear  1 1\n')
ctl_EOF.write('tdef '+str(test_size)+'  linear jan0001 1yr\n')
ctl_EOF.write('vars   1\n')
ctl_EOF.write('pr    1   1  variable\n')
ctl_EOF.write('ENDVARS\n')

print('validation complete')













