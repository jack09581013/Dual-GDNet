from dataset.dataset import *
from torch.utils.data import DataLoader
import numpy as np
from profile import *
from colorama import Style
import profile

# GTX 1660 TiTi
max_disparity = 192  # KITTI 2015
# max_disparity = 144  # flyingthings3D
# max_disparity = 160  # flyingthings3D
# version = 592
version = None
seed = 0
lr_check = False
max_disparity_diff = 1.5
merge_cost = True
candidate = False
plot_and_save_image = False

# produce disparity methods
use_crop_size = False
use_resize = False  # only KITTI_2015_benchmark uses this, and it also doesn't have crop_size setting
use_padding_crop_size = True

if use_resize + use_crop_size + use_padding_crop_size != 1:
    raise Exception('Using only one image regeneration method')

dataset = ['flyingthings3D', 'KITTI_2015', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation', 'KITTI_2015_benchmark',
           'AerialImagery']
image = ['cleanpass', 'finalpass']  # for flyingthings3D

used_profile = profile.GDNet_sdc6f()
dataset = dataset[2]
if dataset == 'flyingthings3D':
    image = image[1]

model = used_profile.load_model(max_disparity, version)[1]
version, loss_history = used_profile.load_history(version)

print('Using model:', used_profile)
print('Using dataset:', dataset)
print('Max disparity:', max_disparity)
print('Number of parameters: {:,}'.format(sum(p.numel() for p in model.parameters())))
print('Plot and save result image:', plot_and_save_image)
print('Using use resize mode:', use_resize)
print('Using use crop size mode:', use_crop_size)
print('Using use use padding crop size:', use_padding_crop_size)

losses = []
error = []
confidence_error = []
total_eval = []

if use_crop_size:
    if dataset == 'flyingthings3D':
        # height, width = 512, 960
        # height, width = 384, 960  # GDNet_mdc6f
        height, width = 384, 960  # GDNet_sdc6f

    elif dataset in ['KITTI_2015', 'KITTI_2015_benchmark', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation']:
        # height, width = 352, 1216  # GDNet_mdc6f
        height, width = 320, 1216  # GDNet_sdc6f
        # height, width = 336, 1200  # GDNet_dc6f

    elif dataset == 'AerialImagery':
        height, width = AerialImagery.image_size

    if dataset == 'flyingthings3D':
        use_dataset = FlyingThings3D(max_disparity, crop_size=(height, width), type='test', crop_seed=0,
                                     image=image)
        test_dataset = random_subset(use_dataset, 100, seed=seed)

    elif dataset == 'KITTI_2015':
        use_dataset = KITTI_2015(type='train', use_crop_size=True, crop_size=(height, width), crop_seed=0,
                                 untexture_rate=0)
        train_dataset, test_dataset = random_split(use_dataset, train_ratio=0.8, seed=seed)

    elif dataset == 'KITTI_2015_Augmentation':
        use_dataset = KITTI_2015_Augmentation(type='test', use_crop_size=True, crop_size=(height, width), seed=0)
        test_dataset = random_subset(use_dataset, 30, seed=seed)

    elif dataset == 'KITTI_2012_Augmentation':
        use_dataset = KITTI_2012_Augmentation(type='test', use_crop_size=True, crop_size=(height, width), seed=0)
        test_dataset = random_subset(use_dataset, 30, seed=seed)

    elif dataset == 'KITTI_2015_benchmark':
        use_dataset = KITTI_2015_benchmark(use_resize=True, resize=(height, width))
        test_dataset = use_dataset

    elif dataset == 'AerialImagery':
        height, width = AerialImagery.image_size
        test_dataset = AerialImagery()

    else:
        raise Exception('Cannot find dataset: ' + dataset)

elif use_resize:
    if dataset in ['KITTI_2015', 'KITTI_2015_benchmark', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation']:
        # height, width = 352, 1216  # GDNet_mdc6f
        height, width = 384, 1280  # GDNet_sdc6f
        # height, width = 336, 1200  # GDNet_dc6f

    if dataset == 'KITTI_2015':
        use_dataset = KITTI_2015(type='train', untexture_rate=0, use_resize=True, resize=(height, width))
        train_dataset, test_dataset = random_split(use_dataset, train_ratio=0.8, seed=seed)

    elif dataset == 'KITTI_2015_Augmentation':
        use_dataset = KITTI_2015_Augmentation(type='test', use_resize=True, resize=(height, width), seed=0)
        test_dataset = random_subset(use_dataset, 30, seed=seed)

    elif dataset == 'KITTI_2012_Augmentation':
        use_dataset = KITTI_2012_Augmentation(type='test', use_resize=True, resize=(height, width), seed=0)
        test_dataset = random_subset(use_dataset, 30, seed=seed)

    else:
        raise Exception('Cannot find dataset: ' + dataset)

elif use_padding_crop_size:
    if dataset in ['KITTI_2015', 'KITTI_2015_benchmark', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation']:
        # height, width = 352, 1216  # GDNet_mdc6f
        height, width = 384, 1280  # GDNet_sdc6f
        # height, width = 336, 1200  # GDNet_dc6f

    if dataset == 'KITTI_2015_Augmentation':
        use_dataset = KITTI_2015_Augmentation(type='test', use_padding_crop_size=True,
                                              padding_crop_size=(height, width), seed=0)
        test_dataset = random_subset(use_dataset, 30, seed=seed)

    elif dataset == 'KITTI_2012_Augmentation':
        use_dataset = KITTI_2012_Augmentation(type='test', use_padding_crop_size=True,
                                              padding_crop_size=(height, width), seed=0)
        test_dataset = random_subset(use_dataset, 30, seed=seed)

    elif dataset == 'KITTI_2015_benchmark':
        use_dataset = KITTI_2015_benchmark(use_padding_crop_size=True, padding_crop_size=(height, width))
        test_dataset = use_dataset

    else:
        raise Exception('Cannot find dataset: ' + dataset)

print('Image size:', (height, width))
test_loader = DataLoader(test_dataset, batch_size=1, shuffle=False)
print('Number of testing data:', len(test_dataset))
model.eval()
for batch_index, (X, Y) in enumerate(test_loader):
    with torch.no_grad():
        utils.tic()

        eval_dict = used_profile.eval(X, Y, dataset, use_resize=use_resize, use_padding_crop_size=use_padding_crop_size,
                                      use_dataset=use_dataset, merge_cost=merge_cost, regression=True)

        time = utils.timespan_str(utils.toc(True))
        loss_str = f'loss = {utils.threshold_color(eval_dict["epe_loss"])}{eval_dict["epe_loss"]:.3f}{Style.RESET_ALL}'
        error_rate_str = f'{eval_dict["error_sum"] / eval_dict["total_eval"]:.2%}'
        print(f'[{batch_index + 1}/{len(test_loader)} {time}] {loss_str}, error rate = {error_rate_str}')

        losses.append(float(eval_dict["epe_loss"]))
        error.append(float(eval_dict["error_sum"]))
        total_eval.append(float(eval_dict["total_eval"]))

        if merge_cost:
            confidence_error.append(float(eval_dict["CE_avg"]))

        if torch.isnan(eval_dict["epe_loss"]):
            print('detect loss nan in testing')
            exit(1)

        if plot_and_save_image:
            plotter = utils.CostPlotter()

            if dataset == 'KITTI_2015_benchmark':
                plotter.plot_image_disparity(X[0], Y[0, 0], dataset, eval_dict,
                                             max_disparity=max_disparity, use_resize=use_resize,
                                             original_width_height=(
                                                 test_dataset.original_width, test_dataset.original_height),
                                             save_result_file=(f'{used_profile}/{dataset}', batch_index, False,
                                                               error_rate_str))
            else:
                plotter.plot_image_disparity(X[0], Y[0, 0], dataset, eval_dict,
                                             max_disparity=max_disparity,
                                             save_result_file=(f'{used_profile}/{dataset}', batch_index, False,
                                                               error_rate_str))
        # exit(0)
        # os.system('nvidia-smi')

print(f'avg loss = {np.array(losses).mean():.3f}')
print(f'std loss = {np.array(losses).std():.3f}')
print(f'avg error rates = {np.array(error).sum() / np.array(total_eval).sum():.2%}')
if merge_cost:
    print(f'avg confidence error = {np.array(confidence_error).mean():.3f}')
print('Number of test case:', len(losses))
print('Excel format:')
# print(f'v{version - 1}'
#       f'{used_profile}\t{np.array(losses).mean():.3f}\t{np.array(losses).std():.3f}\t'
#       f'{np.array(error).sum() / np.array(total_eval).sum():.2%}\t{np.array(confidence_error).mean():.3f}')

print(f'v{version - 1}\t{np.array(losses).mean():.3f}\t{np.array(losses).std():.3f}\t'
      f'{np.array(error).sum() / np.array(total_eval).sum():.2%}\t{np.array(confidence_error).mean():.3f}')
