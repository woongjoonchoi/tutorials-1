"""
Pretraining VGG from scratch 
============================


**Author:** `WoongJoon Choi <https://github.com/woongjoonchoi>`_

In this tutorial, we will embark on an exciting journey to build and
train a VGG network from scratch using Python and popular deep learning
libraries such as PyTorch. We will dive into the details of the VGG
architecture, understanding its components and the rationale behind its
design.

Our tutorial is designed for both beginners who are new to deep learning
and seasoned practitioners looking to deepen their understanding of CNN
architectures.


"""


######################################################################





import torch.optim as optim
import albumentations as A
import numpy as np


from torchvision.datasets import CIFAR100,CIFAR10,MNIST,ImageNet
import os
from PIL import Image





######################################################################
# We recommend using GPU for this tutorial.
# 

device = 'cuda' if torch.cuda.is_available() else 'cpu'


######################################################################
# Worth point of this tutorial
# ----------------------------
# 


######################################################################
# -  We train the model from scratch using only the configuration
#    presented in the paper.
# 
#    -  we do not use future method, like BatchNormalization,Adam , He
#       initialization.
# 
# -  You can apply to ImageNet Data.
# 
#    -  If you can download the ImageNet Data(140GB), you can apply this
#       tutorial to reproduce Original VGG.
# 
# -  You can learn VGG within the training time suggested in the paper.
# 


######################################################################
# Why Vgg is so popluar ?
# -----------------------
# 


######################################################################
# VGG became a model that attracted attention because it succeeded in
# building deeper layers and dramatically shortening the training time
# compared to alexNet, which was the sota model at the time.:
# 


######################################################################
# VGG Configuration
# -----------------
# 


######################################################################
# We define some configurations suggested in VGG paper . Details about
# this configuration will be explained below section.
# 

DatasetName = 'Cifar' # Cifar ,Cifar10, Mnist , ImageNet

## model configuration

num_classes =   100
# CalTech 257 Cifar 100  Cifar10 10 ,Mnist 10 ImageNet 1000
model_version = None ## you must configure it.

## data configuration

train_min = 256
train_max = None
test_min = 256
test_max = 256

## train configuration

batch_size = 32
lr = 1e-2
momentum = 0.9
weight_decay  = 5e-4
lr_factor = 0.1
epoch = 10
clip= None # model D grad clip 0.7


update_count = int(256/batch_size)
accum_step = int(256/batch_size)
eval_step =26 * accum_step  ## CalTech 5 Cifar 5 Mnist 6 , Cifar10 5 ImageNet  26


## model configuration
xavier_count= 4

last_xavier = -8  ##

except_xavier = None

model_layers =None



######################################################################
# | If your GPU memory is 24GB ,The maximum batch size is 128. But, if you
#   use Colab , We recommend using 32 .
# | You can modify the batch size according to your preference.
# 


######################################################################
# Define dataset
# --------------
# 


######################################################################
# We use ``CIFAR100`` Dataset in this tutorial. In Vgg paper , the authors
# scales image istropically . Then , they apply
# Normalization,RandomCrop,HorizontalFlip . So , we need to override
# CIFAR100 class to apply preprocessing.
# 

class Custom_Cifar(CIFAR100) :
    def __init__(self,root,transform = None,multi=False,s_max=None,s_min=256,download=False,val=False,train=True):

        self.multi = multi
        self.s_max = 512
        self.s_min= 256
        if multi :
            self.S = np.random.randint(low=self.s_min,high=self.s_max)
        else :
            self.S = s_min
            transform = A.Compose(
                    [
                        A.Normalize(mean =(0.5071, 0.4867, 0.4408) , std = (0.2675, 0.2565, 0.2761)),
                        A.SmallestMaxSize(max_size=self.S),
                        A.RandomCrop(height =224,width=224),
                        A.HorizontalFlip(),
                        # A.RGBShift()
                    ]

            )
        super().__init__(root,transform=transform,train=train,download=download)
        self.val =train
        self.multi = multi
    def __getitem__(self, index: int) :
        """
        Args:
            index (int): Index

        Returns:
            tuple: (image, target) where target is index of the target class.
        """
        img, target = self.data[index], self.targets[index]

        # doing this so that it is consistent with all other datasets
        # to return a PIL Image

        img = Image.fromarray(img)

        if img.mode == 'L' : img = img.convert('RGB')
        img=np.array(img,dtype=np.float32)


        if self.transform is not None:
            img = self.transform(image=img)
            if len(img['image'].shape) == 3 and self.val==False :
                img = A.RGBShift()(image=img['image'])
            img = img['image']

        if self.target_transform is not None:
            target = self.target_transform(target)

        img=img.transpose((2,0,1))

        return img, target


######################################################################
# Define Model
# ------------
# 


######################################################################
# | In Vgg paper, they do experiment over 6 models. model A is 11 layers,
#   model B is 13 layers, model C is 16 layers , model D is 16 laeyrs and
#   model D is 19 layers . you can train all version of models to
#   reproduce VGG .
# | ``Config_Channels`` means output channels and ``Config_kernels`` means
#   kerenl size.
# 

import torch
from torch import nn


Config_channels = {
"A" : [64,"M" , 128,  "M"  , 256,256,"M" ,512,512 ,"M" , 512,512,"M"] ,
"A_lrn" : [64,"LRN","M" , 128,  "M"  , 256,256,"M" ,512,512 ,"M" , 512,512,"M"] ,
"B" :[64,64,"M" , 128,128,  "M"  , 256,256,"M" ,512,512 ,"M" , 512,512,"M"]  ,
"C" : [64,64,"M" , 128,128,  "M"  , 256,256,256,"M" ,512,512 ,512,"M" , 512,512,512,"M"] ,
"D" :[64,64,"M" , 128,128,  "M"  , 256,256,256,"M" ,512,512 ,512,"M" , 512,512,512,"M"] ,
"E" :[64,64,"M" , 128,128,  "M"  , 256,256,256,256,"M" ,512,512 ,512,512,"M" , 512,512,512,512,"M"]         ,

}



Config_kernel = {
"A" : [3,2 , 3,  2  , 3,3,2 ,3,3 ,2 , 3,3,2] ,
"A_lrn" : [3,2,2 , 3,  2  , 3,3,2 ,3,3 ,2 , 3,3,2] ,
"B" :[3,3,2 , 3,3,  2  , 3,3,2 ,3,3 ,2 , 3,3,2]  ,
"C" : [3,3,2 , 3,3,  2  , 3,3,1,2 ,3,3 ,1,2 , 3,3,1,2] ,
"D" :[3,3,2 , 3,3,  2  , 3,3,3,2 ,3,3 ,3,2 , 3,3,3,2] ,
"E" :[3,3,2 , 3,3,  2  , 3,3,3,3,2 ,3,3 ,3,3,2 , 3,3,3,3,2]         ,

}


######################################################################
# We define model class that generate model in choice of 6 versions.
# 

def make_feature_extractor(cfg_c,cfg_k):
    feature_extract = []
    in_channels = 3
    i = 1
    for  out_channels , kernel in zip(cfg_c,cfg_k) :
        # print(f"{i} th layer {out_channels} processing")
        if out_channels == "M" :
            feature_extract += [nn.MaxPool2d(kernel,2) ]
        elif out_channels == "LRN":
            feature_extract += [nn.LocalResponseNorm(5,k=2) , nn.ReLU()]
        elif out_channels == 1:
            feature_extract+= [nn.Conv2d(in_channels,out_channels,kernel,stride = 1) , nn.ReLU()]
        else :
            feature_extract+= [nn.Conv2d(in_channels,out_channels,kernel,stride = 1 , padding = 1) , nn.ReLU()]

        if isinstance(out_channels,int) :   in_channels = out_channels
        i+=1
    return nn.Sequential(*feature_extract)


class Model_vgg(nn.Module) :
    def __init__(self,version , num_classes):
        conv_5_out_w ,conv_5_out_h = 7,7
        conv_5_out_dim =512
        conv_1_by_1_1_outchannel = 4096
        conv_1_by_1_2_outchannel = 4096
        self.num_classes = num_classes
        self.linear_out = 4096
        self.xavier_count = xavier_count
        self.last_xavier= last_xavier  ## if >0 , initialize last 3 fully connected noraml distribution
        # conv_1_by_1_3_outchannel = num_classes
        self.except_xavier  = except_xavier

        super().__init__()
        self.feature_extractor = make_feature_extractor(Config_channels[version] , Config_kernel[version])
        self.avgpool = nn.AdaptiveAvgPool2d((1,1))
        self.output_layer = nn.Sequential(
                             nn.Conv2d(conv_5_out_dim  ,conv_1_by_1_1_outchannel ,7) ,
                             nn.ReLU(),
                             nn.Dropout2d(),
                             nn.Conv2d(conv_1_by_1_1_outchannel ,conv_1_by_1_2_outchannel,1 ) ,
                             nn.ReLU(),
                             nn.Dropout2d(),
                             nn.Conv2d(conv_1_by_1_2_outchannel ,num_classes,1 )
                             )


        print('weight initialize')
        self.apply(self._init_weights)
        print('weight intialize end')
    def forward(self,x):
        x = self.feature_extractor(x)
        # x= self.avgpool(x)  ##  If Linear is output, use this
        # x= torch.flatten(x,start_dim = 1) ## If Linear is output, use this
        x = self.output_layer(x)
        x= self.avgpool(x)
        x= torch.flatten(x,start_dim = 1)
        return x


    @torch.no_grad()
    def _init_weights(self,m):

        # print(m)
        if isinstance(m,nn.Conv2d):
            print('-------------')
            print(m.kernel_size)
            print(m.out_channels)
            # if (m.out_channels == self.num_classes or m.out_channels == self.linear_out) and self.last_xavier>0 :
            if self.last_xavier>0 and (self.except_xavier is  None or self.last_xavier!=self.except_xavier):
                print('xavier')
                # self.last_xavier-=1
                nn.init.xavier_uniform_(m.weight)
            elif self.xavier_count >0 :
                print('xavier')
                nn.init.xavier_uniform_(m.weight)
                self.xavier_count-=1
            else :
                std = 0.1
                print(f'normal  std : {std}')

                torch.nn.init.normal_(m.weight,std=std)
                # if (m.out_channels == self.num_classes or m.out_channels == self.linear_out) :
                #     self.last_xavier+=10
            self.last_xavier +=1
            if m.bias is not None :
                print('bias zero init')
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Linear):
            if self.last_xavier >0 :
                nn.init.xavier_uniform_(m.weight)
                self.last_xavier-=1
            else :
                torch.nn.init.normal_(m.weight,std=std)
                self.last_xavier+=1
                print(f'last xavier increase to {self.last_xavier}')
            nn.init.constant_(m.bias, 0)


######################################################################
# Parameter Initialization
# ~~~~~~~~~~~~~~~~~~~~~~~~
# 


######################################################################
# When training Vgg , the authors first train model A , then initialized
# the weights of other models with the weights of model A. Waiting for
# Model A to be trained takes a long time . The authors mention how to
# train with xavier initialization rather than initializing with the
# weights of model A. But, they do not mention how to initialize .
# 
# | To Reproduce Vgg , we use xavier initialization method to initialize
#   weights. We apply initialization to few first layes and last layers.
#   Then , we apply random initialization to other layers.
# | **we must fix stdandrad deviation to 0.1**. If standard deviation is
#   larger than 0.1, the weight get NAN values. For stability, we use 0.1
#   for standard deviation.
# | The ``front_xavier`` means how many layers we initialize with xavier
#   initialization in front of layers and The ``last_xavier`` means how
#   many layers we initializae with xavier initialization in last of
#   layers.
# 
# In My experiment, we can use ``front_xavier`` = 4 , ``last_xavier``\ =5
# in model A, ``front_xavier`` =4 ``last_xavier``\ =7 in model B,C , D and
# ``front_xavier`` =5\ ``last_xavier``\ = 9 in model E . These values work
# fine.
# 


######################################################################
# Training Model
# --------------
# 


######################################################################
# We will define top-k error.
# 

def accuracy(output, target, topk=(1,)):
    """Computes the precision@k for the specified values of k"""
    maxk = max(topk)
    batch_size = target.size(0)

    _, pred = output.topk(maxk, 1, True, True)
    pred = pred.t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))

    res = []
    for k in topk:
        # print(f'top {k}')
        correct_k = correct[:k].reshape(-1).float().sum(0,keepdim=True)
        # res.append(correct_k.mul_(100.0 / batch_size))
        res.append(correct_k)
    return res


######################################################################
# we initiate model and loss function and optimizer and schedulers. In
# vgg, they use softmax output ,Momentum Optimizer , and Scheduling based
# on accuarcy.
# 

model = Model_vgg(model_version,num_classes)
criterion = nn.CrossEntropyLoss()

optimizer = optim.SGD(model.parameters(), lr=lr, weight_decay=weight_decay,nesterov=nestrov,momentum=momentum)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'max',patience=10,threshold=1e-3,eps = 1e-5)



######################################################################
# we use ``CIFAR100`` .
# 

if DatasetName == 'Cifar' :
    train_data = Custom_Cifar(root=os.getcwd(),download=True)
    val_data  = Custom_Cifar(root=os.getcwd(),train=False,download=True)
    val_data.val= True
    val_data.s_min = test_min
    val_data.transform=    A.Compose(
                    [
                        A.Normalize(mean =(0.5071, 0.4867, 0.4408) , std = (0.2675, 0.2565, 0.2761)),
                        A.SmallestMaxSize(max_size=val_data.S),
                        A.CenterCrop(height =224,width=224),
                        # A.HorizontalFlip(),
                        # A.RGBShift()
                    ]

                )

train_loader = torch.utils.data.DataLoader(train_data,batch_size= batch_size,shuffle = True , num_workers=4,pin_memory = True,prefetch_factor = 2,drop_last = True)
val_loader = torch.utils.data.DataLoader(val_data,batch_size= batch_size,shuffle = True , num_workers=4,pin_memory = True,prefetch_factor = 2,drop_last = True)


######################################################################
# we set grad_clip to 1.0 for prevent gradient exploding.
# 

model = model.to(device)

grad_clip = 1.0

for e in range(epoch-resume_epoch) :
    print(f'Training Epoch : {e}')
    total_loss = 0
    val_iter = iter(val_loader)
    train_acc=[0,0]
    train_num = 0

    total_acc = [0,0]
    count= 0
    for i , data in tqdm(enumerate(train_loader)) :


        model.train()
        img,label= data
        img,label =img.to(device, non_blocking=True) ,label.to(device, non_blocking=True)

        output = model(img)

        loss = criterion(output,label) /accum_step

        temp_output ,temp_label = output.detach().to('cpu') , label.detach().to('cpu')
        temp_acc = accuracy(temp_output,temp_label,(1,5))
        train_acc=[train_acc[0]+temp_acc[0] , train_acc[1]+temp_acc[1]]
        train_num+=batch_size
        temp_output,temp_label,temp_acc = None,None,None

        loss.backward()
        total_loss += loss.detach().to('cpu')
        img,label=None,None
        torch.cuda.empty_cache()
        if i> 0 and i%update_count == 0 :
            print(f'Training steps : {i}  parameter update loss :{total_loss} ')
            if grad_clip is not None:
                # print(f'Training steps : {i}  parameter grad clip to {grad_clip}')
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)

            if total_loss < 7.0 :
                # print(f"train loss {total_loss}less than 7.0  ,set grad clip to {clip}")
                grad_clip = clip
            if i % eval_step != 0 :
                total_loss = 0

            output,loss = None,None
            torch.cuda.empty_cache()
        if i>0 and i % eval_step == 0 :

            print(f'train losss :{total_loss}')
            temp_loss = total_loss
            total_loss= 0

            val_loss = 0
            torch.cuda.empty_cache()

            for j   in tqdm(range(update_count)) :
                loss = None
                print(f'Evaluation Steps Start')
                try :
                    img,label = next(val_iter)
                except StopIteration :
                    val_iter= iter(val_loader)
                    img,label = next(val_iter)
                with torch.no_grad():
                    model.eval()

                    img , label = img.to(device, non_blocking=True) , label.to(device, non_blocking=True)
                    output = model(img)
                    temp_output ,temp_label = output.detach().to('cpu') , label.detach().to('cpu')
                    temp_acc = accuracy(temp_output,temp_label,(1,5))
                    total_acc=[total_acc[0]+temp_acc[0] , total_acc[1]+temp_acc[1]]
                    count+=batch_size

                    loss = criterion(output,label)/accum_step
                    val_loss += loss.detach().to('cpu')
                    # loss.backward()
                    torch.cuda.empty_cache()


                    img,label,output ,loss= None,None,None,None



                torch.cuda.empty_cache()

            if abs(val_loss-temp_loss) > 0.03 :
                grad_clip=clip
                # print(f"val_loss {val_loss} - train_loss {temp_loss} = {abs(val_loss-temp_loss)} > 0.3")
                # print(f"set grad clip to {grad_clip}")

                best_val_loss = val_loss

            val_loss = None
        img,label,output = None,None,None



    print(f'top 1 val acc : {total_acc[0]}  top 5 val acc : {total_acc[1]}')
    print(f'val_size :{count}')
    top_1_acc ,top_5_acc   = 100*total_acc[0]/count, 100*total_acc[1]/count
    print(f'top 1 val acc  %: {top_1_acc}')
    print(f'top 5 val acc  %: {top_5_acc}')


    print(f'top 1 train acc : {train_acc[0]}  top 5 train acc : {train_acc[1]}')
    print(f'train_size :{train_num}')
    top_1_train ,top_5_train   = 100*train_acc[0]/train_num, 100*train_acc[1]/train_num
    print(f'top 1 train acc  %: {top_1_train}')
    print(f'top 5 train acc  %: {top_5_train}')


    scheduler.step(top_5_acc)



######################################################################
# (Optional) ImageNet
# -------------------
# 

class Cusotm_ImageNet(ImageNet) :
    def __init__(self,root,transform = None,multi=False,s_max=None,s_min=256,split=None,val=False):

        self.multi = multi
        self.s_max = 512
        self.s_min= 256
        if multi :
            self.S = np.random.randint(low=self.s_min,high=self.s_max)
        else :
            self.S = s_min
            transform = A.Compose(
                    [
                        A.Normalize(),
                        A.SmallestMaxSize(max_size=self.S),
                        A.RandomCrop(height =224,width=224),
                        A.HorizontalFlip(),
                        # A.RGBShift()
                    ]

            )
        super().__init__(root,transform=transform,split=split)
        self.val =val
        self.multi = multi
    def __getitem__(self, index: int) :
        """
        Args:
            index (int): Index

        Returns:
            tuple: (image, target) where target is index of the target class.
        """
        path, target = self.samples[index]
        img = self.loader(path)
        # doing this so that it is consistent with all other datasets
        # to return a PIL Image
        img=np.array(img)
        img = Image.fromarray(img)

        if img.mode == 'L' : img = img.convert('RGB')
        img=np.array(img,dtype=np.float32)

        # print(self.transform)

        if self.transform is not None:
            img = self.transform(image=img)
            if len(img['image'].shape) == 3 and self.val==False :
                img = A.RGBShift()(image=img['image'])
            img = img['image']

        if self.target_transform is not None:
            target = self.target_transform(target)
        # print(img)
        img=img.transpose((2,0,1))

        return img, target

if DatasetName == 'ImageNet' :
    train_data= Cusotm_ImageNet(root='ImageNet',split='train')
    val_data= Cusotm_ImageNet('ImageNet',split='val',val=True)
    val_data.val= True
    val_data.s_min = test_min
    val_data.transform=    A.Compose(
                    [
                        A.Normalize(),
                        A.SmallestMaxSize(max_size=val_data.S),
                        A.CenterCrop(height =224,width=224),
                        # A.HorizontalFlip(),
                        # A.RGBShift()
                    ]

                )

######################################################################
# Conculsion
# ----------
# We have seen how pretraining VGG from scratch . This Tutorial will be helpful to reproduce another Foundation Model .

######################################################################
# More things to try
# ------------------
# - Trying On ImageNet
# - Try All version of Model
# - Try All evaluation method in VGG paper


######################################################################
# Further Reading
# ---------------

# - `VGG training using python script <https://github.com/woongjoonchoi/DeepLearningPaper-Reproducing/tree/master/Vgg>`__
# - `VGG paper <https://arxiv.org/abs/1409.1556>`__