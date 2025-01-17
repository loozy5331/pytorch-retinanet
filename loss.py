from __future__ import print_function

import torch
import torch.nn as nn
import torch.nn.functional as F

from utils import one_hot_embedding
from torch.autograd import Variable


# class FocalLoss(nn.Module):
#     def __init__(self, num_classes=20):
#         super(FocalLoss, self).__init__()
#         self.num_classes = num_classes

#     def focal_loss(self, x, y):
#         '''Focal loss.

#         Args:
#           x: (tensor) sized [N,D].
#           y: (tensor) sized [N,].

#         Return:
#           (tensor) focal loss.
#         '''
#         alpha = 0.25
#         gamma = 2

#         t = one_hot_embedding(y.data.cpu(), 1+self.num_classes)  # [N,21]
#         t = t[:,1:]  # exclude background
#         t = Variable(t).cuda()  # [N,20]

#         p = x.sigmoid()
#         pt = p*t + (1-p)*(1-t)         # pt = p if t > 0 else 1-p
#         w = alpha*t + (1-alpha)*(1-t)  # w = alpha if t > 0 else 1-alpha
#         w = w * (1-pt).pow(gamma)
#         return F.binary_cross_entropy_with_logits(x, t, w, size_average=False)

#     def focal_loss_alt(self, x, y):
#         '''Focal loss alternative.

#         Args:
#           x: (tensor) sized [N,D].
#           y: (tensor) sized [N,].

#         Return:
#           (tensor) focal loss.
#         '''
#         alpha = 0.25

#         t = one_hot_embedding(y.data.cpu(), 1+self.num_classes)
#         t = t[:,1:]
#         t = Variable(t).cuda()

#         xt = x*(2*t-1)  # xt = x if t > 0 else -x
#         pt = (2*xt+1).sigmoid()

#         w = alpha*t + (1-alpha)*(1-t)
#         loss = -w*pt.log() / 2
#         return loss.sum()

#     def forward(self, loc_preds, loc_targets, cls_preds, cls_targets):
#         '''Compute loss between (loc_preds, loc_targets) and (cls_preds, cls_targets).

#         Args:
#           loc_preds: (tensor) predicted locations, sized [batch_size, #anchors, 4].
#           loc_targets: (tensor) encoded target locations, sized [batch_size, #anchors, 4].
#           cls_preds: (tensor) predicted class confidences, sized [batch_size, #anchors, #classes].
#           cls_targets: (tensor) encoded target labels, sized [batch_size, #anchors].

#         loss:
#           (tensor) loss = SmoothL1Loss(loc_preds, loc_targets) + FocalLoss(cls_preds, cls_targets).
#         '''
#         batch_size, num_boxes = cls_targets.size()
#         pos = cls_targets > 0  # [N,#anchors]
#         num_pos = pos.data.long().sum()

#         print(loc_preds)

#         ################################################################
#         # loc_loss = SmoothL1Loss(pos_loc_preds, pos_loc_targets)
#         ################################################################
#         mask = pos.unsqueeze(2).expand_as(loc_preds)       # [N,#anchors,4]
#         masked_loc_preds = loc_preds[mask].view(-1,4)      # [#pos,4]
#         masked_loc_targets = loc_targets[mask].view(-1,4)  # [#pos,4]
#         loc_loss = F.smooth_l1_loss(masked_loc_preds, masked_loc_targets, size_average=False)

#         ################################################################
#         # cls_loss = FocalLoss(loc_preds, loc_targets)
#         ################################################################
#         pos_neg = cls_targets > -1  # exclude ignored anchors
#         mask = pos_neg.unsqueeze(2).expand_as(cls_preds)
#         masked_cls_preds = cls_preds[mask].view(-1,self.num_classes)
#         cls_loss = self.focal_loss_alt(masked_cls_preds, cls_targets[pos_neg])
#         loc_loss = loc_loss.view(batch_size, 1)
#         cls_loss = cls_loss.view(batch_size, 1)

#         print('loc_loss: %.3f | cls_loss: %.3f' % (loc_loss.data[0]/num_pos, cls_loss.data[0]/num_pos), end=' | ')
#         loss = (loc_loss+cls_loss)/num_pos
#         return loss

class FocalLoss(nn.Module):
    def __init__(self, num_classes):
        super(FocalLoss, self).__init__()
        self.num_classes = num_classes

    def _one_hot_embeding(self, labels):
        """Embeding labels to one-hot form.
        Args:
            labels(LongTensor): class labels
            num_classes(int): number of classes
        Returns:
            encoded labels, sized[N, #classes]
        """

        y = torch.eye(self.num_classes+1)  # [D, D]
        return y[labels]  # [N, D]

    def focal_loss(self, x, y):
        """Focal loss
        Args:
            x(tensor): size [N, D]
            y(tensor): size [N, ]
        Returns:
            (tensor): focal loss
        """

        alpha = 0.25
        gamma = 2

        t = self._one_hot_embeding(y.data.cpu())  # [N, num_classes]
        t = t[:, 1:]  # exclude background
        t = Variable(t).cuda()  # [N, num_classes]
        
        logit = F.softmax(x)
        logit = logit.clamp(1e-7, 1.-1e-7)
        conf_loss_tmp = -1 * t.float() * torch.log(logit)
        conf_loss_tmp = alpha * conf_loss_tmp * (1-logit)**gamma
        conf_loss = conf_loss_tmp.sum()

        return conf_loss

    def forward(self, loc_preds, loc_targets, cls_preds, cls_targets):
        """Compute loss between (loc_preds, loc_targets) and (cls_preds, cls_targets).
        Args:
          loc_preds(tensor): predicted locations, sized [batch_size, #anchors, 4].
          loc_targets(tensor): encoded target locations, sized [batch_size, #anchors, 4].
          cls_preds(tensor): predicted class confidences, sized [batch_size, #anchors, #classes].
          cls_targets(tensor): encoded target labels, sized [batch_size, #anchors].
        Returns:
          (tensor) loss = SmoothL1Loss(loc_preds, loc_targets) + FocalLoss(cls_preds, cls_targets).
        """

        pos = cls_targets > 0  # [N,#anchors]
        num_pos = pos.data.long().sum()

        # loc_loss = SmoothL1Loss(pos_loc_preds, pos_loc_targets)
        mask = pos.unsqueeze(2).expand_as(loc_preds)  # [N,#anchors,4]
        masked_loc_preds = loc_preds[mask].view(-1, 4)  # [#pos,4]
        masked_loc_targets = loc_targets[mask].view(-1, 4)  # [#pos,4]
        loc_loss = F.smooth_l1_loss(masked_loc_preds, masked_loc_targets, size_average=False)

        # cls_loss = FocalLoss(loc_preds, loc_targets)
        pos_neg = cls_targets > -1  # exclude ignored anchors
        # num_pos_neg = pos_neg.data.long().sum()
        mask = pos_neg.unsqueeze(2).expand_as(cls_preds)
        masked_cls_preds = cls_preds[mask].view(-1, self.num_classes)

        cls_loss = self.focal_loss(masked_cls_preds, cls_targets[pos_neg])
        num_pos = max(1.0, num_pos.item())

        # print('loc_loss: %.3f | cls_loss: %.3f' % (loc_loss.item() / num_pos, cls_loss.item() / num_pos), end=' | ')

        loss = loc_loss / num_pos + cls_loss / num_pos

        return loss