#!/usr/bin/env python
import os
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
import tensorflow as tf
import numpy as np
import math
from netCDF4 import Dataset
from tempfile import TemporaryFile

num_convf = convfilter
num_hiddf = hiddfilter
xdim = xxx
ydim = yyy
zdim = zzz
xdim2 = int(xdim/4)
ydim2 = int(ydim/4)
num_ens = int(numberensemble)
test_size = int(nd_size-st_size)

def init_weights(shape):
    return tf.Variable(tf.random.normal(shape, stddev=1))

def init_bias(shape):
    return tf.Variable(tf.random.uniform(shape, minval=-0.01, maxval=0.01))

# Input Data
inpv1 = np.zeros((test_size,zdim,ydim,xdim), dtype=np.float32)
inp1 = Dataset('/home/jhkim/samfile','r')
inpv1[:,0:3,:,:] = inp1.variables['sst'][st_size:nd_size,:,:,:]
inpv1[:,3:6,:,:] = inp1.variables['t300'][st_size:nd_size,:,:,:]

tdim = int(inpv1.shape[0])
print('tdim= ',tdim)

# reshape training data (tdim,zdim,ydim,xdim) -> (tdim,xdim,ydim,zdim)
ftX = np.swapaxes(inpv1,1,3)

# Tensors
ftX = ftX.reshape(-1, xdim, ydim, zdim)
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
l1a = tf.nn.conv2d(X, filters=w, strides=[1, 1, 1, 1], padding='SAME') + b
l1b = tf.tanh(l1a)
l1 = tf.nn.max_pool2d(input=l1b, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
l1 = tf.nn.dropout(l1, rate=1 - (p_keep_conv))

l2a = tf.nn.conv2d(l1, filters=w2, strides=[1, 1, 1, 1], padding='SAME') + b2
l2b = tf.tanh(l2a)
l2 = tf.nn.max_pool2d(input=l2b, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')
l2 = tf.nn.dropout(l2, rate=1 - (p_keep_conv))

l3a = tf.nn.conv2d(l2, filters=w3, strides=[1, 1, 1, 1], padding='SAME') + b3
l3b = tf.tanh(l3a)
l3 = tf.reshape(l3b, [-1, w4.get_shape().as_list()[0]])
l3 = tf.nn.dropout(l3, rate=1 - (p_keep_conv))

l4 = tf.tanh(tf.matmul(l3, w4) + b4)
l4 = tf.nn.dropout(l4, rate=1 - (p_keep_hidden))

py_x = tf.matmul(l4, w_o) + b_o

saver = tf.compat.v1.train.Saver()

config = tf.compat.v1.ConfigProto()
config.gpu_options.allow_growth = True

# Launch the graph in a session
with tf.compat.v1.Session() as sess:
    tf.compat.v1.global_variables_initializer().run()

    en_mean = np.zeros((tdim,xdim2,ydim2))
    for k in range(tdim):
      print('tdim: '+str(k+1))
      sum_f = np.zeros((xdim2,ydim2,num_ens))
      for i in range(num_ens):

        saver.restore(sess,'home_directory/output/model_name/opfname/EN'+str(i+1)+'/model.ckpt')
   
        conv1 = sess.run(l3b, feed_dict={X: ftX[k,:,:,:].reshape(1,xdim,ydim,zdim), 
                              p_keep_conv:1.0, p_keep_hidden:1.0})

        conv2 = sess.run(w4,  feed_dict={X: ftX[k,:,:,:].reshape(1,xdim,ydim,zdim),  
                              p_keep_conv:1.0, p_keep_hidden:1.0})

        conv3 = sess.run(w_o, feed_dict={X: ftX[k,:,:,:].reshape(1,xdim,ydim,zdim), 
                              p_keep_conv:1.0, p_keep_hidden:1.0})

        conv4 = sess.run(b4,  feed_dict={X: ftX[k,:,:,:].reshape(1,xdim,ydim,zdim),
                              p_keep_conv:1.0, p_keep_hidden:1.0})

        conv5 = sess.run(b_o, feed_dict={X: ftX[k,:,:,:].reshape(1,xdim,ydim,zdim),
                              p_keep_conv:1.0, p_keep_hidden:1.0})
  
        mul_w = np.zeros((xdim2,ydim2,num_hiddf))
        conv1 = conv1.reshape(xdim2,ydim2,num_convf)
        conv2 = conv2.reshape(xdim2,ydim2,num_convf,num_hiddf)
        conv3 = conv3.reshape(num_hiddf)
        conv4 = conv4.reshape(num_hiddf)/(num_convf*xdim2*ydim2)
        conv5 = conv5.reshape(1)/(xdim2*ydim2*num_hiddf)
  
        for j in range(num_hiddf):
          mul_w[:,:,j] = sess.run(conv3[j]*tf.tanh(np.sum(conv1[:,:,:]*conv2[:,:,:,j]+conv4[j],axis=2)))
          
        sum_f[:,:,i] = np.mean(mul_w,axis=2)+conv5

      en_mean[k,:,:] = np.mean(sum_f,axis=2)

    # save heatmap (4-byte binary)
    en_mean.astype('float32').tofile('home_directory/output/case/heatmap/opfname/heatmap.gdat')

# make CTL file (for GrADS)
ctl_EOF = open('home_directory/output/case/heatmap/opfname/heatmap.ctl','w')
ctl_EOF.write('dset ^heatmap.gdat\n')
ctl_EOF.write('undef -9.99e+08\n')
ctl_EOF.write('xdef   '+str(xdim2)+'  linear  0.  20\n')
ctl_EOF.write('ydef   '+str(ydim2)+'  linear -90.  20\n')
ctl_EOF.write('zdef    1  levels  1000\n')
ctl_EOF.write('tdef '+str(tdim)+'  linear jan0001 1yr\n')
ctl_EOF.write('vars   1\n')
ctl_EOF.write('pr    1   1  variable\n')
ctl_EOF.write('ENDVARS\n')


