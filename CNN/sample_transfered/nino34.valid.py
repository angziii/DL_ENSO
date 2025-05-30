#!/usr/bin/env python
import os
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
import tensorflow as tf
import numpy as np
from netCDF4 import Dataset
from tempfile import TemporaryFile

tg_mn = int(target_mon - 1)
ld_mn1 = int(23 - lead_mon + tg_mn)
ld_mn2 = int(23 - lead_mon + tg_mn + 3)
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
inp1 = Dataset('/home/jhkim/data/GODAS/samfile','r')

inpv1 = np.zeros((int(tot_size - sample_size),zzz,yyy,xxx))
inpv1[:,0:3,:,:] = inp1.variables['sst'][sample_size:tot_size,ld_mn1:ld_mn2,:,:] 
inpv1[:,3:6,:,:] = inp1.variables['t300'][sample_size:tot_size,ld_mn1:ld_mn2,:,:]

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
  w_o = init_weights([num_hiddf, 1])
  b_o = init_bias([1])
  
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

saver = tf.compat.v1.train.Saver()
config = tf.compat.v1.ConfigProto()
config.gpu_options.allow_growth = True

# Launch the graph in a session
with tf.compat.v1.Session(config=config) as sess:
    tf.compat.v1.global_variables_initializer().run()

    saver.restore(sess,'home_directory/output/case/opfname/ENmember/model.ckpt')

    result = sess.run(py_x, feed_dict={X: teX, p_keep_conv:1.0, 
                      p_keep_hidden:1.0})

    result.astype('float32').tofile('home_directory/output/case/opfname/ENmember/result.gdat')

print('validation complete')












