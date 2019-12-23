'''
    python -m visdom.server
    http://localhost:8097

    tensorboard --logdir=runs
    http://localhost:6006/

    ONNX export failed on ATen operator ifft because torch.onnx.symbolic.ifft does not exist
'''

from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
import visdom
import matplotlib.pyplot as plt
import numpy as np
import torchvision
from torchvision import datasets, transforms

def matplotlib_imshow(img, one_channel=False):
    if one_channel:
        img = img.mean(dim=0)
    img = img / 2 + 0.5     # unnormalize
    npimg = img.numpy()
    if one_channel:
        plt.imshow(npimg, cmap="Greys")
    else:
        plt.imshow(np.transpose(npimg, (1, 2, 0)))
    plt.show()


class Visualize:
    def __init__(self,env_title="onnet", **kwargs):
        self.log_dir = f'runs/{env_title}'
        self.loss_step = 0
        self.writer = SummaryWriter(self.log_dir)

    def ShowModel(self,model,data_loader):
        '''
            tensorboar显示效果较差
        '''
        dataiter = iter(data_loader)
        images, labels = dataiter.next()
        if images.shape[0]>32:
            images=images[0:32,...]
        if True:
            img_grid = torchvision.utils.make_grid(images)
            matplotlib_imshow(img_grid, one_channel=True)
            self.writer.add_image('one_batch', img_grid)
            self.writer.close()
        image_1 = images[0:1,:,:,:]
        if False:
            images = images.cuda()
            self.writer.add_graph(model,images )
            self.writer.close()

    def UpdateLoss(self,tag,loss,global_step=None):
        step = self.loss_step if global_step==None else global_step
        with SummaryWriter(log_dir=self.log_dir) as writer:
            writer.add_scalar(tag, loss, global_step=step)
        #self.writer.close()  # 执行close立即刷新，否则将每120秒自动刷新
        self.loss_step = self.loss_step+1

class  Visdom_Visualizer(Visualize):
    '''
    封装了visdom的基本操作，但是你仍然可以通过`self.vis.function`
    调用原生的visdom接口
    '''

    def __init__(self,env_title, **kwargs):
        super(Visdom_Visualizer, self).__init__(env_title)
        self.viz = visdom.Visdom(env=env_title, **kwargs)

        # 画的第几个数，相当于横座标
        # 保存（’loss',23） 即loss的第23个点
        # self.index = {}
        # self.log_text = ''

    def UpdateLoss(self, title,legend, loss, yLabel='LOSS',global_step=None):
        self.vis_plot( self.loss_step, loss, title,legend,yLabel)
        self.loss_step = self.loss_step + 1

    def vis_plot(self,epoch, loss_, title,legend,yLabel):
        self.viz.line(X=torch.FloatTensor([epoch]), Y=torch.FloatTensor([loss_]), win='loss',
                 opts=dict(
                     legend=[legend],  # [config_.use_bn],
                     fillarea=False,
                     showlegend=True,
                     width=1600,
                     height=800,
                     xlabel='Epoch',
                     ylabel=yLabel,
                     # ytype='log',
                     title=title,
                     # marginleft=30,
                     # marginright=30,
                     # marginbottom=80,
                     # margintop=30,
                 ),
                 update='append' if epoch > 0 else None)

    def reinit(self, env='default', **kwargs):
        '''
        修改visdom的配置
        '''
        self.vis = visdom.Visdom(env=env, **kwargs)
        return self

    def plot_many(self, d):
        '''
        一次plot多个
        @params d: dict (name,value) i.e. ('loss',0.11)
        '''
        for k, v in d.iteritems():
            self.plot(k, v)

    def img_many(self, d):
        for k, v in d.iteritems():
            self.img(k, v)

    def plot(self, name, y, **kwargs):
        '''
        self.plot('loss',1.00)
        '''
        x = self.index.get(name, 0)
        self.vis.line(Y=np.array([y]), X=np.array([x]),
                      win=name,
                      opts=dict(title=name),
                      update=None if x == 0 else 'append',
                      **kwargs
                      )
        self.index[name] = x + 1

    def img(self, name, img_, **kwargs):
        '''
        self.img('input_img',t.Tensor(64,64))
        self.img('input_imgs',t.Tensor(3,64,64))
        self.img('input_imgs',t.Tensor(100,1,64,64))
        self.img('input_imgs',t.Tensor(100,3,64,64),nrows=10)

        ！！！don‘t ~~self.img('input_imgs',t.Tensor(100,64,64),nrows=10)~~！！！
        '''
        self.vis.images(img_.cpu().numpy(),
                        win=(name),
                        opts=dict(title=name),
                        **kwargs
                        )

    def log(self, info, win='log_text'):
        '''
        self.log({'loss':1,'lr':0.0001})
        '''

        self.log_text += ('[{time}] {info} <br>'.format(
            time=time.strftime('%m%d_%H%M%S'), \
            info=info))
        self.vis.text(self.log_text, win)
        print(self.log_text)

    def __getattr__(self, name):
        return getattr(self.vis, name)

def PROJECTOR_test():
    """ ==================使用PROJECTOR对高维向量可视化====================
        https://blog.csdn.net/wsp_1138886114/article/details/87602112
        PROJECTOR的的原理是通过PCA，T-SNE等方法将高维向量投影到三维坐标系（降维度）。
        Embedding Projector从模型运行过程中保存的checkpoint文件中读取数据，
        默认使用主成分分析法（PCA）将高维数据投影到3D空间中，也可以通过设置设置选择T-SNE投影方法，
        这里做一个简单的展示。
    """
    log_dirs = "../../runs/projector/"
    BATCH_SIZE = 256
    EPOCHS = 2
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_loader = DataLoader(datasets.MNIST('../../data', train=True, download=False,
                                             transform=transforms.Compose([
                                                 transforms.ToTensor(),
                                                 transforms.Normalize((0.1307,), (0.3081,))
                                             ])),
                              batch_size=BATCH_SIZE, shuffle=True)

    test_loader = torch.utils.data.DataLoader(
        datasets.MNIST('../../data', train=False, transform=transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,))
        ])),
        batch_size=BATCH_SIZE, shuffle=True)

    class ConvNet(nn.Module):
        def __init__(self):
            super().__init__()
            # 1,28x28
            self.conv1 = nn.Conv2d(1, 10, 5)  # 10, 24x24
            self.conv2 = nn.Conv2d(10, 20, 3)  # 128, 10x10
            self.fc1 = nn.Linear(20 * 10 * 10, 500)
            self.fc2 = nn.Linear(500, 10)

        def forward(self, x):
            in_size = x.size(0)
            out = self.conv1(x)  # 24
            out = F.relu(out)
            out = F.max_pool2d(out, 2, 2)  # 12
            out = self.conv2(out)  # 10
            out = F.relu(out)
            out = out.view(in_size, -1)
            out = self.fc1(out)
            out = F.relu(out)
            out = self.fc2(out)
            out = F.log_softmax(out, dim=1)
            return out

    model = ConvNet().to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters())

    def train(model, DEVICE, train_loader, optimizer, epoch):
        n_iter = 0
        model.train()
        for batch_idx, (data, target) in enumerate(train_loader):
            data, target = data.to(DEVICE), target.to(DEVICE)
            optimizer.zero_grad()
            output = model(data)
            loss = F.nll_loss(output, target)
            loss.backward()
            optimizer.step()
            if (batch_idx + 1) % 30 == 0:
                n_iter = n_iter + 1
                print('Train Epoch: {} [{}/{} ({:.0f}%)]\t Loss: {:.6f}'.format(
                    epoch, batch_idx * len(data), len(train_loader.dataset),
                           100. * batch_idx / len(train_loader), loss.item()))

                # 主要增加了一下内容
                out = torch.cat((output.data.cpu(), torch.ones(len(output), 1)), 1)  # 因为是投影到3D的空间，所以我们只需要3个维度
                with SummaryWriter(log_dir=log_dirs, comment='mnist') as writer:
                    # 使用add_embedding方法进行可视化展示
                    writer.add_embedding(
                        out,
                        metadata=target.data,
                        label_img=data.data,
                        global_step=n_iter)

    def test(model, device, test_loader):
        model.eval()
        test_loss = 0
        correct = 0
        with torch.no_grad():
            for data, target in test_loader:
                data, target = data.to(device), target.to(device)
                output = model(data)
                test_loss += F.nll_loss(output, target, reduction='sum').item()  # 损失相加
                pred = output.max(1, keepdim=True)[1]  # 找到概率最大的下标
                correct += pred.eq(target.view_as(pred)).sum().item()

        test_loss /= len(test_loader.dataset)
        print('\n Test set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'
              .format(test_loss, correct, len(test_loader.dataset),100. * correct / len(test_loader.dataset)))

    for epoch in range(1, EPOCHS + 1):
        train(model, DEVICE, train_loader, optimizer, epoch)
        test(model, DEVICE, test_loader)

    # 保存模型
    torch.save(model.state_dict(), './pytorch_tensorboardX_03.pth')

if __name__ == '__main__':
    PROJECTOR_test()