from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import oneflow as flow
# from core.resnet_module import make_bottleneck_layer, make_basic_layer
from core.resnet_module import *
#import datetime

import os
# time = datetime.datetime.now().strftime('_%f')
#time = datetime.datetime.now().strftime('%Y-%m-%d-%H_%M_%S_%f')

def _conv2d_layer(name,
        input,
        filters,
        kernel_size,
        strides=1,
        padding="VALID",
        groups_num=1,
        data_format="NHWC",
        # dilation_rate=1,
        # activation='Relu',
        use_bias=True,
        # use_bn=True,
        weight_initializer=flow.glorot_uniform_initializer(),
        bias_initializer=flow.zeros_initializer(),
        trainable=True,
        groups=1,
        ):
    
    return flow.layers.conv2d(
                input, filters, kernel_size, strides, padding,
                data_format=data_format, dilation_rate=1, groups=groups,
                activation=None, use_bias=use_bias,
                kernel_initializer=flow.xavier_normal_initializer(),
                bias_initializer=flow.zeros_initializer(),
                # kernel_regularizer=flow.variance_scaling_initializer(2.0, mode="fan_out", distribution="random_normal", data_format="NHWC"),
                # bias_regularizer=flow.zeros_initializer(),
                trainable=trainable, name=name)


def _batch_norm(inputs, momentum, epsilon, name, training=True):
    
    return flow.layers.batch_normalization(
        inputs=inputs,
        axis=-1,
        momentum=momentum,
        epsilon=epsilon,
        center=True,
        scale=True,
        # beta_initializer=flow.zeros_initializer(),
        # gamma_initializer=flow.ones_initializer(),
        # beta_regularizer=flow.zeros_initializer(),
        # gamma_regularizer=flow.ones_initializer(),
        moving_mean_initializer=flow.zeros_initializer(),
        moving_variance_initializer=flow.ones_initializer(),
        trainable=True,
        training=training,
        name=name
    )

def bottleneck_block(inputs, filters_num, strides=1, downsample=False,
                     name='bottleneck', training=True):
    expansion = 4

    residual = inputs

    x = _conv2d_layer(f'{name}_conv1', inputs,  filters_num//expansion, 1, padding="SAME", use_bias=False)
    x = _batch_norm(x, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1', training=training)
    x = flow.nn.relu(x, name=f'{name}_relu1')
    x = _conv2d_layer(f'{name}_conv2', x, filters_num//expansion, 3, strides, padding="SAME", use_bias=False)
    x = _batch_norm(x, momentum=0.1, epsilon=1e-5, name=f'{name}_bn2', training=training)
    x = flow.nn.relu(x, name=f'{name}_relu2')

    x = _conv2d_layer(f'{name}_conv3', x, filters_num, 1, 1, use_bias=False)
    x = _batch_norm(x, momentum=0.1, epsilon=1e-5, name=f'{name}_bn3', training=training)


    if downsample:
        residual = _conv2d_layer(f'{name}_down_conv', inputs, filters_num, 1, strides, use_bias=False)
        residual = _batch_norm(residual, momentum=0.1, epsilon=1e-5, name=f'{name}_down_bn', training=training)

    output = flow.nn.relu(flow.math.add_n([x, residual],name=f'{name}_res'), name=f'{name}_out')

    return output

def transion_layer1(inputs, filters=[32, 64], name='stage1_transition', training=None):

    x1 = _conv2d_layer(f'{name}_conv1', inputs, filters[0], 3, 1, padding="SAME")
    x1 = _batch_norm(x1, momentum=0.1, epsilon=1e-5, training=training, name=f'{name}_bn1')
    x1 = flow.nn.relu(x1, name=f'{name}_relu1')

    x2 = _conv2d_layer(f'{name}_conv2', inputs, filters[1], 3, 2, padding="SAME", use_bias=False)
    x2 = _batch_norm(x2, momentum=0.1, epsilon=1e-5, name=f'{name}_bn2' , training=training)
    x2 = flow.nn.relu(x2, name=f'{name}_relu2')
    return [x1, x2]

def make_branch(inputs, filters, name='branch', training=None):
    x = basic_block(inputs, filters, downsample=False, name=f'{name}_basic1', training=training)
    x = basic_block(x, filters, downsample=False, name=f'{name}_basic2', training=training)
    x = basic_block(x, filters, downsample=False, name=f'{name}_basic3', training=training)
    x = basic_block(x, filters, downsample=False, name=f'{name}_basic4', training=training)
    return x

def basic_block(inputs, filters, strides=1,training=True, downsample=False, name='basic'):
    expansion = 1
    residual = inputs

    x = _conv2d_layer(f'{name}_conv1', inputs, filters//expansion, 3, strides, padding="SAME")
    x = _batch_norm(x, momentum=0.1, epsilon=1e-5, training=training, name=f'{name}_bn1')
    x = flow.nn.relu(x)

    x = _conv2d_layer(f'{name}_conv2', x, filters//expansion, 3, 1, padding="SAME")
    x = _batch_norm(x, momentum=0.1, epsilon=1e-5, training=training, name=f'{name}_bn2')
    if downsample:
        residual = _conv2d_layer(f'{name}_down_conv', inputs, filters, 1, strides,)
        residual = _batch_norm(residual, momentum=0.1, epsilon=1e-5, name=f'{name}_down_bn')

    output = flow.nn.relu(flow.math.add(x, residual,name=f'{name}_res'), name=f'{name}_out')

    return output


def fuse_layer1(inputs, filters=[32, 64], name='stage2_fuse', training=None):
    x1, x2 = inputs

    x11 = x1

    x21 = _conv2d_layer(f'{name}_conv_2_1', x2, filters[0], 1, 1,
                          use_bias=False)
    x21 = _batch_norm(x21, momentum=0.1, epsilon=1e-5, name=f'{name}_bn_2_1', training=training)
    x21 = flow.layers.upsample_2d(x=x21,size=(2,2),data_format="NHWC", name=f'{name}_up_2_1')
    x1 = flow.nn.relu(flow.math.add_n([x11, x21],name=f'{name}_add1'), name=f'{name}_branch1_out')


    x22 = x2
    x12 = _conv2d_layer(f'{name}_conv1_2', x1, filters[1], 3, 2, padding="SAME",
                          use_bias=False)
    x12 = _batch_norm(x12, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_2', training=training)
    x2 = flow.nn.relu(flow.math.add_n([x12, x22],name=f'{name}_add2'), name=f'{name}_branch2_out')

    return [x1, x2]

def transition_layer2(inputs, filters, name='stage2_transition', training=None):
    x1, x2 = inputs

    x1 = _conv2d_layer(f'{name}_conv1', x1, filters[0], 3, 1, padding="SAME",
                          use_bias=False)
    x1 = _batch_norm(x1, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1', training=training)
    x1 = flow.nn.relu(x1, name=f'{name}_relu1')

    x21 = _conv2d_layer(f'{name}_conv2', x2, filters[1], 3, 1, padding="SAME",
                          use_bias=False)
    x21 = _batch_norm(x21, momentum=0.1, epsilon=1e-5, name=f'{name}_bn2', training=training)
    x21 = flow.nn.relu(x21, name=f'{name}_relu2')

    x22 = _conv2d_layer(f'{name}_conv3', x2, filters[2], 3, 2, padding="SAME",
                          use_bias=False)
    x22 = _batch_norm(x22, momentum=0.1, epsilon=1e-5, name=f'{name}_bn3', training=training)
    x22 = flow.nn.relu(x22, name=f'{name}_relu3')
    return [x1, x21, x22]

def fuse_layer2(inputs, filters=[32, 64, 128], name='stage3_fuse', training=None):
    x1, x2, x3 = inputs

    # branch 1
    x11 = x1

    x21 = _conv2d_layer(f'{name}_conv2_1', x2, filters[0], 1, 1,
                          use_bias=False)
    x21 = _batch_norm(x21, momentum=0.1, epsilon=1e-5, name=f'{name}_bn2_1', training=training)
    x21 = flow.layers.upsample_2d(x=x21, size=(2, 2), data_format="NHWC", name=f'{name}_up2_1')

    x31 = _conv2d_layer(f'{name}_conv3_1',x3, filters[0], 1, 1,
                          use_bias=False)
    x31 = _batch_norm(x31, momentum=0.1, epsilon=1e-5, name=f'{name}_bn3_1', training=training)
    x31 = flow.layers.upsample_2d(x=x31, size=(4,4), data_format="NHWC", name=f'{name}_up3_1')

    x1 = flow.nn.relu(flow.math.add_n([x11, x21, x31],name=f'{name}_add1'), name=f'{name}_branch1_out')

    # branch 2
    x22 = x2

    x12 = _conv2d_layer(f'{name}_conv1_2',x1, filters[1], 3, 2, padding="SAME",
                          use_bias=False)
    x12 = _batch_norm(x12, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_2', training=training)

    x32 = _conv2d_layer(f'{name}_conv3_2', x3, filters[1], 1, 1,
                           use_bias=False)
    x32 = _batch_norm(x32, momentum=0.1, epsilon=1e-5, name=f'{name}_bn3_2', training=training)
    x32 = flow.layers.upsample_2d(x=x32, size=(2, 2), data_format="NHWC", name=f'{name}_up3_2')

    x2 = flow.nn.relu(flow.math.add_n([x12, x22, x32], name=f'{name}_add2'), name=f'{name}_branch2_out')

    # branch 3
    x33 = x3

    x13 = _conv2d_layer(f'{name}_conv1_3_1', x1, filters[0], 3, 2, padding="SAME",
                           use_bias=False)
    x13 = _batch_norm(x13, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_3_1', training=training)
    x13 = flow.nn.relu(x13,name=f'{name}_relu1_3_1')
    x13 = _conv2d_layer(f'{name}_conv1_3_2', x13, filters[2], 3, 2, padding="SAME",
                           use_bias=False)
    x13 = _batch_norm(x13, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_3_2', training=training)

    x23 = _conv2d_layer(f'{name}_conv2_3', x2, filters[2], 3, 2, padding="SAME",
                           use_bias=False)
    x23 = _batch_norm(x23, momentum=0.1, epsilon=1e-5, name=f'{name}_bn2_3', training=training)

    x3 = flow.nn.relu(flow.math.add_n([x13, x23, x33],name=f'{name}_add3'), name=f'{name}_branch3_out')

    return [x1, x2, x3]

def transition_layer3(inputs, filters, name='stage3_transition', training=None):
    x1, x2, x3 = inputs

    x1 = _conv2d_layer(f'{name}_conv1', x1, filters[0], kernel_size=3, strides=1, padding="SAME",
                           use_bias=False)
    x1 = _batch_norm(x1, momentum=0.1, epsilon=1e-5, name=f'{name}_bn_1', training=training)
    x1 = flow.nn.relu(x1,name=f'{name}_relu_1')

    x2 = _conv2d_layer(f'{name}_conv2', x2, filters[1], kernel_size=3, strides=1, padding="SAME",
                           use_bias=False)
    x2 = _batch_norm(x2, momentum=0.1, epsilon=1e-5, name=f'{name}_bn_2', training=training)
    x2 = flow.nn.relu(x2,name=f'{name}_relu_2')

    x31 = _conv2d_layer(f'{name}_conv3', x3, filters[2], kernel_size=3, strides=1, padding="SAME",
                           use_bias=False)
    x31 = _batch_norm(x31, momentum=0.1, epsilon=1e-5, name=f'{name}_bn_3', training=training)
    x31 = flow.nn.relu(x31,name=f'{name}_relu_3')


    x32 = _conv2d_layer(f'{name}_conv4', x3, filters[3], kernel_size=3, strides=2, padding="SAME",
                           use_bias=False)
    x32 = _batch_norm(x32, momentum=0.1, epsilon=1e-5, name=f'{name}_bn_4', training=training)
    x32 = flow.nn.relu(x32,name=f'{name}_relu_4')


    return [x1, x2, x31, x32]

def fuse_layer3(inputs, filters=[32, 64, 128, 256], name='stage4_fuse', training=None):
    x1, x2, x3, x4 = inputs

    # branch 1
    x11 = x1

    x21 = _conv2d_layer(f'{name}_conv2_1', x2, filters[0], 1, 1,
                           use_bias=False)
    x21 = _batch_norm(x21, momentum=0.1, epsilon=1e-5, name=f'{name}_bn21', training=training)
    x21 = flow.layers.upsample_2d(x=x21, size=(2, 2), data_format="NHWC", name=f'{name}_up2_1')

    x31 =  _conv2d_layer(f'{name}_conv3_1', x3, filters[0], 1, 1,
                           use_bias=False)
    x31 = _batch_norm(x31, momentum=0.1, epsilon=1e-5, name=f'{name}_bn31', training=training)
    x31 = flow.layers.upsample_2d(x=x31, size=(4,4), data_format="NHWC", name=f'{name}_up3_1')

    x41 = _conv2d_layer(f'{name}_conv4_1', x4, filters[0], 1, 1,
                           use_bias=False)
    x41 = _batch_norm(x41, momentum=0.1, epsilon=1e-5, name=f'{name}_bn4_1', training=training)
    x41 = flow.layers.upsample_2d(x=x41, size=(8, 8), data_format="NHWC", name=f'{name}_up4_1')

    x1 = flow.nn.relu(flow.math.add_n([x11, x21, x31, x41],name=f'{name}_add1'), name=f'{name}_branch1_out')

    # branch 2
    x22 = x2

    x12 = _conv2d_layer(f'{name}_conv1_2', x1, filters[1], 3, 2, padding="SAME",
                           use_bias=False)
    x12 = _batch_norm(x12, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_2', training=training)

    x32 = _conv2d_layer(f'{name}_conv3_2', x3, filters[1], 1, 1,
                           use_bias=False)
    x32 = _batch_norm(x32, momentum=0.1, epsilon=1e-5, name=f'{name}_bn3_2', training=training)
    x32 = flow.layers.upsample_2d(x=x32, size=(2,2), data_format="NHWC", name=f'{name}_up3_2')


    x42 = _conv2d_layer(f'{name}_conv4_2', x4, filters[1], 1, 1,
                           use_bias=False)
    x42 =  _batch_norm(x42, momentum=0.1, epsilon=1e-5, name=f'{name}_bn4_2' , training=training)
    x42 =  flow.layers.upsample_2d(x=x42, size=(4,4), data_format="NHWC", name=f'{name}_up4_2')

    x2 = flow.nn.relu(flow.math.add_n([x12, x22, x32, x42],name=f'{name}_add2'), name=f'{name}_branch2_out')

    # branch 3
    x33 = x3

    x13 = _conv2d_layer(f'{name}_conv1_3_1', x1, filters[0], 3, 2, padding="SAME",
                           use_bias=False)
    x13 = _batch_norm(x13, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_3_1', training=training)
    x13 = flow.nn.relu(x13,name=f'{name}_relu1_3_1')

    x13 = _conv2d_layer(f'{name}_conv1_3_2', x13, filters[2], 3, 2, padding="SAME",
                           use_bias=False)
    x13 = _batch_norm(x13, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_3_2', training=training)


    x23 = _conv2d_layer(f'{name}_conv2_3', x2, filters[2], 3, 2, padding="SAME",
                           use_bias=False)
    x23 = _batch_norm(x23, momentum=0.1, epsilon=1e-5, name=f'{name}_bn23', training=training)

    x43 = _conv2d_layer(f'{name}_conv4_3', x4, filters[2], 1, 1,
                           use_bias=False)
    x43 = _batch_norm(x43, momentum=0.1, epsilon=1e-5, name=f'{name}_bn423', training=training)
    x43 = flow.layers.upsample_2d(x=x43, size=(2,2), data_format="NHWC", name=f'{name}_up4_3')

    x3 = flow.nn.relu(flow.math.add_n([x13, x23, x33, x43],name=f'{name}_add3'), name=f'{name}_branch3_out')

    # branch 4
    x44 = x4

    x14 = _conv2d_layer(f'{name}_conv1_4_1', x1, filters[0], 3, 2, padding="SAME",
                           use_bias=False)
    x14 = _batch_norm(x14, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_4_1', training=training)
    x14 = flow.nn.relu(x14,name=f'{name}_relu1_4_1')
    x14 = _conv2d_layer(f'{name}_conv1_4_2', x14, filters[0], 3, 2, padding="SAME",
                        use_bias=False)
    x14 = _batch_norm(x14, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_4_2', training=training)
    x14 = flow.nn.relu(x14, name=f'{name}_relu1_4_2')
    x14 = _conv2d_layer(f'{name}_conv1_4_3', x14, filters[3], 3, 2, padding="SAME",
                        use_bias=False)
    x14 = _batch_norm(x14, momentum=0.1, epsilon=1e-5, name=f'{name}_bn1_4_3', training=training)


    x24 = _conv2d_layer(f'{name}_conv2_4_1',x2, filters[1], 3, 2, padding="SAME",
                           use_bias=False)
    x24 = _batch_norm(x24, momentum=0.1, epsilon=1e-5, name=f'{name}_bn2_4_1', training=training)
    x24 = flow.nn.relu(x24, name=f'{name}_relu2_4_1')
    x24 = _conv2d_layer(f'{name}_conv2_4_2',x24, filters[3], 3, 2, padding="SAME",
                        use_bias=False)
    x24 = _batch_norm(x24, momentum=0.1, epsilon=1e-5, name=f'{name}_bn2_4_2', training=training)


    x34 = _conv2d_layer(f'{name}_conv3_4',x3, filters[3], 3, 2, padding="SAME",
                           use_bias=False)
    x34 = _batch_norm(x34, momentum=0.1, epsilon=1e-5, name=f'{name}_bn3_4', training=training)

    x4 = flow.nn.relu(flow.math.add_n([x14, x24, x34, x44],name=f'{name}_add4'), name=f'{name}_branch4_out')

    return [x1, x2, x3, x4]

def fuse_layer4(inputs, filters=32, name='final_fuse', training=None):
    x1, x2, x3, x4 = inputs

    x11 = x1

    x21 = _conv2d_layer(f'{name}_conv2_1',x2, filters, 1, 1,
                           use_bias=False)
    x21 = _batch_norm(x21, momentum=0.1, epsilon=1e-5, name=f'{name}_bn2_1', training=training)
    x21 = flow.layers.upsample_2d(x=x21, size=(2,2), data_format="NHWC", name=f'{name}_up2_1')

    x31 = _conv2d_layer(f'{name}_conv3_1',x3, filters, 1, 1,
                           use_bias=False)
    x31 = _batch_norm(x31, momentum=0.1, epsilon=1e-5, name=f'{name}_bn3_1', training=training)
    x31 = flow.layers.upsample_2d(x=x31, size=(4,4), data_format="NHWC", name=f'{name}_up3_1')

    x41 = _conv2d_layer(f'{name}_conv4_1',x4, filters, 1, 1,
                           use_bias=False)
    x41 = _batch_norm(x41, momentum=0.1, epsilon=1e-5, name=f'{name}_bn4_1', training=training)
    x41 = flow.layers.upsample_2d(x=x41, size=(8,8), data_format="NHWC", name=f'{name}_up4_1')

    x = flow.concat(inputs=[x11, x21, x31, x41],axis=-1,name=f'{name}_out')
    return x




def HRNet(img_input,
          training=None
          ):
    # STAGE 1
    x = _conv2d_layer('stage1_stem_conv1', img_input, 64, 3, 2, padding="SAME", use_bias=False)
    x = _batch_norm(x, momentum=0.1, epsilon=1e-5, name='stage1_stem_bn1', training=training)
    x = flow.nn.relu(x, name='stage1_stem_relu1')
    
    x = _conv2d_layer('stage1_stem_conv2', x, 64, 3, 2, padding="SAME", use_bias=False)
    x = _batch_norm(x, momentum=0.1, epsilon=1e-5, name='stage1_stem__bn2', training=training)
    x = flow.nn.relu(x, name='stage1_stem__relu2')

    x = bottleneck_block(x, 256, downsample=True, name='stage1_bottleneck1', training=training)
    x = bottleneck_block(x, 256, downsample=False, name='stage1_bottleneck2', training=training)
    x = bottleneck_block(x, 256, downsample=False, name='stage1_bottleneck3', training=training)
    x = bottleneck_block(x, 256, downsample=False, name='stage1_bottleneck4', training=training)
    x1, x2 = transion_layer1(x, filters=[32, 64], name='stage1_transition', training=training)

    # STAGE 2
    x1 = make_branch(x1, 32, name='stage2_branch1', training=training)
    x2 = make_branch(x2, 64, name='stage2_branch2', training=training)
    x1, x2 = fuse_layer1([x1, x2], filters=[32, 64], name='stage2_fuse', training=training)
    x1, x2, x3 = transition_layer2([x1, x2], filters=[32, 64, 128],
                                   name='stage2_transition', training=training)

    # STAGE 3
    for i in range(4):
        x1 = make_branch(x1, 32, name=f'stage3_{i + 1}_branch1', training=training)
        x2 = make_branch(x2, 64, name=f'stage3_{i + 1}_branch2', training=training)
        x3 = make_branch(x3, 128, name=f'stage3_{i + 1}_branch3', training=training)
        x1, x2, x3 = fuse_layer2([x1, x2, x3], filters=[32, 64, 128],
                                 name=f'stage3_{i + 1}_fuse', training=training)

    x1, x2, x3, x4 = transition_layer3([x1, x2, x3], filters=[32, 64, 128, 256],
                                       name='stage3_transition', training=training)

    # STAGE 4
    for i in range(3):
        x1 = make_branch(x1, 32, name=f'stage4_{i + 1}_branch1', training=training)
        x2 = make_branch(x2, 64, name=f'stage4_{i + 1}_branch2', training=training)
        x3 = make_branch(x3, 128, name=f'stage4_{i + 1}_branch3', training=training)
        x4 = make_branch(x4, 256, name=f'stage4_{i + 1}_branch4', training=training)
        if i != 2:
            x1, x2, x3, x4 = fuse_layer3([x1, x2, x3, x4],
                                         filters=[32, 64, 128, 256],
                                         name=f'stage4_{i + 1}_fuse', training=training)
        else:
            x = fuse_layer4([x1, x2, x3, x4], 32, name=f'stage4_{i + 1}_fuse', training=training)

    x = _conv2d_layer('predictions', x, 17, 1, 1)

    return x

    