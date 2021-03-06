from __future__ import print_function
import os
import argparse
import torch
import torch.backends.cudnn as cudnn
from torch.autograd import Variable
from data import VOCroot, BaseTransform
from data import AnnotationTransform_handles, HandlesDetection
from data import AnnotationTransformVOC, VOCDetection
from ssd import build_ssd

VOC_CLASSES = (  # always index 0
      'aeroplane', 'bicycle', 'bird', 'boat',
      'bottle', 'bus', 'car', 'cat', 'chair',
      'cow', 'diningtable', 'dog', 'horse',
      'motorbike', 'person', 'pottedplant',
      'sheep', 'sofa', 'train', 'tvmonitor')

HANDLES_CLASSES = ('door', 'handle')


parser = argparse.ArgumentParser(description='Single Shot MultiBox Detection')
parser.add_argument('--trained_model', required=True, type=str,
                    help='Trained state_dict file path to open')
parser.add_argument('--save_folder', default='eval/', type=str,
                    help='Dir to save results')
parser.add_argument('--visual_threshold', default=0.6, type=float,
                    help='Final confidence threshold')
parser.add_argument('--no-cuda', action='store_false', dest='cuda',
                    help='Use cuda to train model')
parser.add_argument('--data_root', default=VOCroot,
                    help='Location of VOC root directory')

args = parser.parse_args()

if not os.path.exists(args.save_folder):
    os.mkdir(args.save_folder)


def test_net(save_folder, net, cuda, testset, transform, thresh):
    # dump predictions and assoc. ground truth to text file for now
    filename = save_folder+'test1.txt'
    num_images = len(testset)
    for i in range(num_images):
        print('Testing image {:d}/{:d}....'.format(i+1, num_images))
        img = testset.pull_image(i)
        img_id, annotation = testset.pull_anno(i)
        x = torch.from_numpy(transform(img)[0]).permute(2, 0, 1)
        x = Variable(x.unsqueeze(0))

        with open(filename, mode='a') as f:
            f.write('\nGROUND TRUTH FOR: '+img_id+'\n')
            for box in annotation:
                f.write('label: '+' || '.join(str(b) for b in box)+'\n')
        if cuda:
            x = x.cuda()

        y = net(x)      # forward pass
        detections = y.data
        # scale each detection back up to the image
        scale = torch.Tensor([img.shape[1], img.shape[0],
                             img.shape[1], img.shape[0]])
        pred_num = 0
        with open(filename, mode='a') as f:
            f.write('PREDICTIONS: '+'\n')

        for i in range(detections.size(1)):
            j = 0
            while detections[0, i, j, 0] >= 0.6:
                score = detections[0, i, j, 0]
                label_name = labelmap[i-1]
                pt = (detections[0, i, j, 1:]*scale).cpu().numpy()
                coords = (pt[0], pt[1], pt[2], pt[3])
                pred_num += 1
                with open(filename, mode='a') as f:
                    f.write(str(pred_num) +
                            ' label: ' + label_name +
                            ' score: ' + str(score) +
                            ' ' + ' || '.join(str(c) for c in coords) + '\n')
                j += 1


if __name__ == '__main__':
    # load net
    if 'handle' in args.data_root:
        num_classes = len(HANDLES_CLASSES) + 1  # +1 background
        testset = HandlesDetection(args.data_root, None,
                                   AnnotationTransform_handles(),
                                   dataset='test')
        labelmap = HANDLES_CLASSES
    else:
        num_classes = len(VOC_CLASSES) + 1  # +1 background
        testset = VOCDetection(args.data_root,
                               [('2007', 'test')], None,
                               AnnotationTransformVOC())
        labelmap = VOC_CLASSES

    net = build_ssd('test', 300, num_classes)  # initialize SSD
    net.load_weights(args.trained_model)
    net.eval()
    print('Finished loading model!')

    if args.cuda:
        net = net.cuda()
        cudnn.benchmark = True

    # evaluation
    test_net(args.save_folder, net, args.cuda, testset,
             BaseTransform(net.size, (104, 117, 123)),
             thresh=args.visual_threshold)
