from dataset.dataset import *
from torch.utils.data import DataLoader
import numpy as np
from profile import *
from colorama import Style
import profile
import utils.cost_volume as cv

def main():
    # GTX 1660 TiTi
    max_disparity = 192  # KITTI 2015
    # max_disparity = 160  # flyingthings3D
    version = 1200
    seed = 0
    merge_cost = True
    use_crop_size = False
    use_resize = False
    use_padding_crop_size = True

    # CostPlotter Settings
    plot_and_save_image = False
    plot_and_show_image = True
    show_index = None
    plot_threshold = 0.015
    use_confidence_error_cost = False
    use_candidate_error = plot_and_show_image

    if use_resize + use_crop_size + use_padding_crop_size != 1:
        raise Exception('Using only one image regeneration method')

    dataset_name = ['flyingthings3D', 'KITTI_2015', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation',
                    'KITTI_2015_benchmark', 'AerialImagery'][2]

    used_profile = profile.GDNet_sdc6f()
    dataloader_kwargs = {'num_workers': 8, 'pin_memory': True, 'drop_last': True}

    model = used_profile.load_model(max_disparity, version)[1]
    version, loss_history = used_profile.load_history(version)
    # torch.backends.cudnn.benchmark = True

    print('Using model:', used_profile)
    print('Using dataset:', dataset_name)
    print('Max disparity:', max_disparity)
    print('Number of parameters: {:,}'.format(sum(p.numel() for p in model.parameters())))
    print('Plot and save result image:', plot_and_save_image)
    print('Using use crop size mode:', use_crop_size)
    print('Using use resize mode:', use_resize)
    print('Using use use padding crop size:', use_padding_crop_size)

    losses = []
    error = []
    confidence_error = []
    total_eval = []
    show_index_count = 0
    is_show = False

    if use_crop_size:
        if dataset_name == 'flyingthings3D':
            # height, width = 512, 960
            # height, width = 384, 960  # GDNet_mdc6f
            height, width = 384, 960  # GDNet_sdc6f

        elif dataset_name in ['KITTI_2015', 'KITTI_2015_benchmark', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation']:
            # height, width = 352, 1216  # GDNet_mdc6f
            height, width = 320, 1216  # GDNet_sdc6f
            # height, width = 336, 1200  # GDNet_dc6f

        elif dataset_name == 'AerialImagery':
            height, width = AerialImagery.image_size

        if dataset_name == 'flyingthings3D':
            use_dataset = FlyingThings3D(max_disparity, type='test', use_crop_size=True, crop_size=(height, width),
                                         crop_seed=0, image='finalpass')
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        elif dataset_name == 'KITTI_2015':
            use_dataset = KITTI_2015(type='train', use_crop_size=True, crop_size=(height, width), crop_seed=0,
                                     untexture_rate=0)
            train_dataset, test_dataset = random_split(use_dataset, train_ratio=0.8, seed=seed)

        elif dataset_name == 'KITTI_2015_Augmentation':
            use_dataset = KITTI_2015_Augmentation(type='test', use_crop_size=True, crop_size=(height, width), seed=0)
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        elif dataset_name == 'KITTI_2012_Augmentation':
            use_dataset = KITTI_2012_Augmentation(type='test', use_crop_size=True, crop_size=(height, width), seed=0)
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        elif dataset_name == 'AerialImagery':
            height, width = AerialImagery.image_size
            test_dataset = AerialImagery()

        else:
            raise Exception('Cannot find dataset: ' + dataset_name)

    elif use_resize:
        if dataset_name == 'flyingthings3D':
            # height, width =   # GDNet_mdc6f
            height, width = 576, 960  # GDNet_sdc6f
            # height, width =   # GDNet_dc6f

        elif dataset_name in ['KITTI_2015', 'KITTI_2015_benchmark', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation']:
            # height, width = 352, 1216  # GDNet_mdc6f
            height, width = 384, 1280  # GDNet_sdc6f
            # height, width = 336, 1200  # GDNet_dc6f
            # height, width = 384, 1272  # LEAStereo_fdcf

        if dataset_name == 'flyingthings3D':
            use_dataset = FlyingThings3D(max_disparity, type='test', use_resize=True,
                                         resize=(height, width), image='finalpass')
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        elif dataset_name == 'KITTI_2015':
            use_dataset = KITTI_2015(type='train', untexture_rate=0, use_resize=True, resize=(height, width))
            train_dataset, test_dataset = random_split(use_dataset, train_ratio=0.8, seed=seed)

        elif dataset_name == 'KITTI_2015_Augmentation':
            use_dataset = KITTI_2015_Augmentation(type='test', use_resize=True, resize=(height, width), seed=0)
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        elif dataset_name == 'KITTI_2012_Augmentation':
            use_dataset = KITTI_2012_Augmentation(type='test', use_resize=True, resize=(height, width), seed=0)
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        else:
            raise Exception('Cannot find dataset: ' + dataset_name)

    elif use_padding_crop_size:
        if dataset_name == 'flyingthings3D':
            # height, width =   # GDNet_mdc6f
            height, width = 576, 960  # GDNet_sdc6f, LEAStereo_fdcf
            # height, width =   # GDNet_dc6f

        elif dataset_name in ['KITTI_2015', 'KITTI_2015_benchmark', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation']:
            # height, width = 352, 1216  # GDNet_mdc6f
            height, width = 384, 1280  # GDNet_sdc6f
            # height, width = 336, 1200  # GDNet_dc6f
            # height, width = 384, 1272  # LEAStereo_fdcf

        if dataset_name == 'flyingthings3D':
            use_dataset = FlyingThings3D(max_disparity, type='test', use_padding_crop_size=True,
                                         padding_crop_size=(height, width), image='finalpass')
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        elif dataset_name == 'KITTI_2015':
            use_dataset = KITTI_2015(type='train', untexture_rate=0, use_padding_crop_size=True,
                                     padding_crop_size=(height, width))
            train_dataset, test_dataset = random_split(use_dataset, train_ratio=0.8, seed=seed)

        elif dataset_name == 'KITTI_2015_Augmentation':
            use_dataset = KITTI_2015_Augmentation(type='test', use_padding_crop_size=True,
                                                  padding_crop_size=(height, width), shuffle_seed=0)
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        elif dataset_name == 'KITTI_2012_Augmentation':
            use_dataset = KITTI_2012_Augmentation(type='test', use_padding_crop_size=True,
                                                  padding_crop_size=(height, width), shuffle_seed=0)
            test_dataset = random_subset(use_dataset, 30, seed=seed)

        elif dataset_name == 'KITTI_2015_benchmark':
            use_dataset = KITTI_2015_benchmark(use_padding_crop_size=True, padding_crop_size=(height, width))
            test_dataset = use_dataset

        else:
            raise Exception('Cannot find dataset: ' + dataset_name)

    print('Image size:', (height, width))
    test_loader = DataLoader(test_dataset, batch_size=1, shuffle=False, **dataloader_kwargs)
    print('Number of testing data:', len(test_dataset))

    if plot_and_show_image and show_index is not None:
        assert 1 <= show_index <= len(test_dataset)

    model.eval()
    for batch_index, (X, Y, pass_info) in enumerate(test_loader):
        X, Y = X.cuda(), Y.cuda()
        show_index_count += 1

        if plot_and_show_image and show_index is not None and show_index_count < show_index:
            print(f'Skip batch: {show_index_count}')
            is_show = True
            continue

        if plot_and_save_image and is_show:
            exit()

        with torch.no_grad():
            utils.tic()

            if isinstance(used_profile, profile.GDNet_class_regression_basic):
                eval_dict = used_profile.eval(X, Y, pass_info, dataset_name, use_resize=use_resize,
                                              use_padding_crop_size=use_padding_crop_size,
                                              merge_cost=merge_cost, regression=True,
                                              use_confidence_error_cost=use_confidence_error_cost,
                                              use_candidate_error=use_candidate_error)

            elif isinstance(used_profile, profile.GDNet_disparity_regression_basic):
                eval_dict = used_profile.eval(X, Y, pass_info, dataset_name, use_resize=use_resize,
                                              use_padding_crop_size=use_padding_crop_size)

            time = utils.timespan_str(utils.toc(True))
            loss_str = f'loss = {utils.threshold_color(eval_dict["epe_loss"])}{eval_dict["epe_loss"]:.3f}{Style.RESET_ALL}'
            error_rate_str = f'{eval_dict["error_sum"] / eval_dict["total_eval"]:.2%}'
            print(f'[{batch_index + 1}/{len(test_loader)} {time}] {loss_str}, error rate = {error_rate_str}')

            losses.append(float(eval_dict["epe_loss"]))
            error.append(float(eval_dict["error_sum"]))
            total_eval.append(float(eval_dict["total_eval"]))

            if isinstance(used_profile, profile.GDNet_class_regression_basic):
                confidence_error.append(float(eval_dict["CE_avg"]))

            if torch.isnan(eval_dict["epe_loss"]):
                print('detect loss nan in testing')
                exit(1)

            if plot_and_save_image:
                plotter = utils.CostPlotter()
                plotter.plot_image_disparity(X[0], Y[0, 0], dataset_name, eval_dict,
                                             max_disparity=max_disparity, use_resize=use_resize,
                                             use_padding_crop_size=use_padding_crop_size, pass_info=pass_info,
                                             save_result_file=(f'{used_profile}/{dataset_name}', batch_index, False,
                                                               error_rate_str))

            if plot_and_show_image and eval_dict["error_sum"] / eval_dict["total_eval"] > plot_threshold:
                plotter = utils.CostPlotter()
                cost_volume_data = []

                if eval_dict["cost_left"] is not None:
                    cv_data = cv.CostVolumeData(str(used_profile), - eval_dict["cost_left"])
                    cv_data.line_style = '-'
                    cost_volume_data.append(cv_data)

                if eval_dict["flip_cost"] is not None:
                    cv_data = cv.CostVolumeData(str(used_profile) + ' Flipped', - eval_dict["flip_cost"])
                    cv_data.line_style = '-'
                    cost_volume_data.append(cv_data)

                if eval_dict["cost_merge"] is not None:
                    cv_data = cv.CostVolumeData(str(used_profile) + ' Merged', - eval_dict["cost_merge"],
                                                eval_dict["disp"])
                    cv_data.line_style = '-'
                    cost_volume_data.append(cv_data)

                plotter.cost_volume_data = cost_volume_data
                plotter.plot_image_disparity(X[0], Y[0, 0], dataset_name, eval_dict,
                                             max_disparity=max_disparity, use_resize=use_resize,
                                             use_padding_crop_size=use_padding_crop_size, pass_info=pass_info)
            # exit(0)
            # os.system('nvidia-smi')

    print(f'avg loss = {np.array(losses).mean():.3f}')
    print(f'std loss = {np.array(losses).std():.3f}')
    print(f'avg error rates = {np.array(error).sum() / np.array(total_eval).sum():.2%}')
    if isinstance(used_profile, profile.GDNet_class_regression_basic):
        print(f'avg confidence error = {np.array(confidence_error).mean():.3f}')
    print('Number of test case:', len(losses))
    print('Excel format:')
    # print(f'v{version - 1}'
    #       f'{used_profile}\t{np.array(losses).mean():.3f}\t{np.array(losses).std():.3f}\t'
    #       f'{np.array(error).sum() / np.array(total_eval).sum():.2%}\t{np.array(confidence_error).mean():.3f}')

    print(f'v{version - 1}\t{np.array(losses).mean():.3f}\t{np.array(losses).std():.3f}\t'
          f'{np.array(error).sum() / np.array(total_eval).sum():.2%}\t{np.array(confidence_error).mean():.3f}')

if __name__ == '__main__':
    main()