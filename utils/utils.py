import re
import numpy as np
import struct
import cv2
import matplotlib.pyplot as plt
import torch
import os
from colorama import Fore, Style
import sys
import pickle
import datetime
import math


def print_progress(message, rate):
    '''Pring progress'''
    if rate < 0: rate = 0
    if rate > 1: rate = 1
    percent = rate * 100
    sys.stdout.write('\r')
    sys.stdout.write('{} {:.2f} % [{:<50s}]'.format(message, percent, '=' * int(percent / 2)))
    sys.stdout.flush()


def save(obj, filename):
    with open(filename, 'wb') as file:
        pickle.dump(obj, file)


def load(filename):
    with open(filename, 'rb') as file:
        return pickle.load(file)


TOOLS_CURRENT_TIME = None


def tic():
    global TOOLS_CURRENT_TIME
    TOOLS_CURRENT_TIME = datetime.datetime.now()


def toc(return_timespan=False):
    global TOOLS_CURRENT_TIME
    if return_timespan:
        return datetime.datetime.now() - TOOLS_CURRENT_TIME
    else:
        print('Elapsed:', datetime.datetime.now() - TOOLS_CURRENT_TIME)


def read_pfm(file):
    # Adopted from https://stackoverflow.com/questions/48809433/read-pfm-format-in-python
    with open(file, "rb") as f:
        # Line 1: PF=>RGB (3 channels), Pf=>Greyscale (1 channel)
        type = f.readline().decode('latin-1')
        if "PF" in type:
            channels = 3
        elif "Pf" in type:
            channels = 1
        else:
            sys.exit(1)

        # Line 2: width height
        line = f.readline().decode('latin-1')
        width, height = re.findall('\d+', line)
        width = int(width)
        height = int(height)

        # Line 3: +ve number means big endian, negative means little endian
        line = f.readline().decode('latin-1')
        BigEndian = True
        if "-" in line:
            BigEndian = False

        # Slurp all binary data
        samples = width * height * channels
        buffer = f.read(samples * 4)

        # Unpack floats with appropriate endianness
        if BigEndian:
            fmt = ">"
        else:
            fmt = "<"
        fmt = fmt + str(samples) + "f"
        img = struct.unpack(fmt, buffer)

        img = np.array(img, dtype=np.float32).reshape(height, width, channels)
        img = np.flip(img, axis=0)
        # return img, height, width
        return img


class RandomCropper:
    def __init__(self, image_size, crop_size, seed=None):
        H, W = crop_size
        assert image_size[0] >= H, 'image height must larger than crop height'
        assert image_size[1] >= W, 'image width must larger than crop width'

        H_range = image_size[0] - H
        W_range = image_size[1] - W

        np.random.seed(seed)
        if H_range > 0:
            self.min_row = np.random.randint(0, H_range + 1)
        else:
            self.min_row = 0

        if W_range > 0:
            self.min_col = np.random.randint(0, W_range + 1)
        else:
            self.min_col = 0

        self.max_row = self.min_row + H
        self.max_col = self.min_col + W

    def crop(self, I):
        return I[..., self.min_row:self.max_row, self.min_col:self.max_col]


def angle_to_hue(angle):
    return np.array(angle / 2, dtype=np.uint8)


def radian_to_hue(radian):
    return np.array(radian / np.pi * 90, dtype=np.uint8)


def xy_to_color(flow):
    h, w = flow.shape[:2]
    hsv = np.zeros((h, w, 3), dtype=np.uint8)
    hsv[..., 1] = 255

    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv[..., 0] = radian_to_hue(ang)
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return rgb


def torch_array_to_bgr(x):
    x = x.data.cpu().numpy().astype('uint8')
    x = x.swapaxes(2, 3).swapaxes(1, 3)
    return x


def version_code(file):
    a = file.index('-')
    b = file.index('.')
    return int(file[a + 1:b])


class CostPlotter:
    RESULT_ROOT = './result/prediction'

    def __init__(self):
        self.fig = None
        self.cost_volume_fig = None
        self.cost_volume_data = []
        self.check_line = None
        self.image_font_size = (24, 18)
        self.cv_font_size = (48, 32, 32)
        self.title_position = [0.5, 1.025]
        os.makedirs(self.RESULT_ROOT, exist_ok=True)
        self.save_detail = None
        self.marker_size = 10

    def plot_image_disparity(self, X, Y, dataset_name, eval_dict, max_disparity=192, padding=30, save_file=None,
                             save_result_file=None, error_map=True, is_benchmark=False, use_resize=False,
                             use_padding_crop_size=False, pass_info=None):
        self.max_disparity = max_disparity
        self.padding = padding
        self.confidence_error = None
        self.confidence_error_cost = None
        self.candidate_error = None
        self.predict = None
        self.error_map = None
        self.dataset_name = dataset_name

        if isinstance(X, torch.Tensor):
            assert X.dim() == 3 and Y.dim() == 2

            if 'disp' in eval_dict.keys() and eval_dict["disp"] is not None:
                self.predict = eval_dict["disp"][0]
                assert self.predict.dim() == 2
                self.predict = self.predict.data.cpu().numpy()

            X = (X * 255).data.cpu().numpy().astype('uint8')
            X = X.swapaxes(1, 2).swapaxes(0, 2)  # hegiht, width, channel*3
            Y = Y.data.cpu().numpy()

            if use_resize:
                X = cv2.resize(X, (pass_info['original_width'], pass_info['original_height']))
                Y = cv2.resize(Y, (pass_info['original_width'], pass_info['original_height']))
                self.predict = cv2.resize(self.predict, (pass_info['original_width'], pass_info['original_height']))
            elif use_padding_crop_size:
                X = X[:pass_info['original_height'], :pass_info['original_width']]
                Y = Y[:pass_info['original_height'], :pass_info['original_width']]

            if 'confidence_error' in eval_dict.keys() and eval_dict["confidence_error"] is not None:
                self.confidence_error = eval_dict["confidence_error"][0].data.cpu().numpy()
            if 'confidence_error_cost' in eval_dict.keys() and eval_dict["confidence_error_cost"] is not None:
                self.confidence_error_cost = eval_dict["confidence_error_cost"][0].data.cpu().numpy()
            if 'candidate_error' in eval_dict.keys() and eval_dict["candidate_error"] is not None:
                self.candidate_error = eval_dict["candidate_error"][0].data.cpu().numpy()

        elif isinstance(X, np.ndarray):
            assert X.ndim == 3 and Y.ndim == 2

            if 'disp' in eval_dict.keys() and eval_dict["disp"] is not None:
                self.predict = eval_dict["disp"][0]
                assert self.predict.dim() == 2
            X = X.swapaxes(1, 2).swapaxes(0, 2)
        else:
            raise Exception('cannot find data type')

        if self.predict is not None and not is_benchmark:
            mask = y_mask(Y, self.max_disparity, dataset_name) & (self.predict != -1)
            self.error_map = np.zeros(Y.shape, dtype=np.float)
            self.error_map[mask] = np.abs(self.predict[mask] - Y[mask])

        self.X = X
        self.Y = Y
        self.eval_dict = eval_dict

        self.fig = plt.figure(figsize=(16, 10))
        self.fig.patch.set_alpha(0)  # Setting the backbround color to opacity 0
        self.fig.canvas.mpl_connect('button_press_event', self.main_onclick)

        plt.subplot(421)
        plt.title('Left Image')
        plt.imshow(X[:, :, 0:3])
        plt.axis('off')

        plt.subplot(422)
        plt.title('Right Image')
        plt.imshow(X[:, :, 3:6])
        plt.axis('off')

        if dataset_name == 'AerialImagery':
            self.vmin = 0
            self.vmax = 123
        else:
            self.vmin = Y.reshape(-1).min()
            self.vmax = Y.reshape(-1).max()

            if self.vmax - self.vmin < 1:
                self.vmin = 0
                self.vmax = 80

        plt.subplot(423)
        plt.title('Ground Truth Disparity')
        plt.imshow(Y, vmin=self.vmin, vmax=self.vmax, cmap='jet')
        plt.axis('off')

        if self.predict is not None:
            plt.subplot(424)
            plt.title(f'Predict Disparity, EPE = {self.eval_dict["epe_loss"]:.3f}')
            plt.imshow(self.predict, vmin=self.vmin, vmax=self.vmax, cmap='jet')
            plt.axis('off')

        if self.error_map is not None and not is_benchmark:
            plt.subplot(425)
            plt.title('Error Map')
            plt.imshow(self.error_map, cmap='jet')
            plt.axis('off')

        if self.confidence_error is not None:
            plt.subplot(426)
            plt.title(f'Confidence Error (avg={eval_dict["CE_avg"]:.3f})')
            plt.imshow(self.confidence_error, cmap='jet')
            plt.axis('off')

        if self.candidate_error is not None:
            plt.subplot(427)
            plt.title(f'Candidate Error')
            plt.imshow(self.candidate_error, cmap='jet')
            plt.axis('off')

        if save_file is not None:
            plt.savefig(save_file, box_inches='tight')

        if save_result_file is not None:
            subfoler, batch_index, display_ground_true, error_rate_str = save_result_file
            if display_ground_true:
                os.makedirs(os.path.join(self.RESULT_ROOT, subfoler, 'left'), exist_ok=True)
                os.makedirs(os.path.join(self.RESULT_ROOT, subfoler, 'right'), exist_ok=True)
                os.makedirs(os.path.join(self.RESULT_ROOT, subfoler, 'ground_true'), exist_ok=True)

                plt.imsave(os.path.join(self.RESULT_ROOT, subfoler, 'left', f'{batch_index}.png'), X[:, :, 0:3])

                plt.imsave(os.path.join(self.RESULT_ROOT, subfoler, 'right', f'{batch_index}.png'), X[:, :, 3:6])

                plt.imsave(os.path.join(self.RESULT_ROOT, subfoler, 'ground_true', f'{batch_index}.png'),
                           Y, vmin=self.vmin, vmax=self.vmax, cmap='jet')

            os.makedirs(os.path.join(self.RESULT_ROOT, subfoler, 'predict'), exist_ok=True)
            os.makedirs(os.path.join(self.RESULT_ROOT, subfoler, 'disp_0'), exist_ok=True)
            if not is_benchmark:
                os.makedirs(os.path.join(self.RESULT_ROOT, subfoler, 'error_map'), exist_ok=True)

            if error_map:
                plt.imsave(os.path.join(self.RESULT_ROOT, subfoler, 'predict', f'{batch_index}.png'),
                           self.predict, vmin=self.vmin, vmax=self.vmax, cmap='jet')

            img = self.predict  # <class 'numpy.ndarray'>, shape: (375, 1242), dtype: float32
            save_path = os.path.join(self.RESULT_ROOT, subfoler, 'disp_0', f'{batch_index:06d}_10.png')
            cv2.imwrite(save_path, (img * 0x100).astype('uint16'))
            if error_map and not is_benchmark:
                plt.imsave(os.path.join(self.RESULT_ROOT, subfoler, 'error_map', f'{batch_index}_{error_rate_str}.png'),
                           self.error_map, vmin=self.vmin, vmax=self.vmax, cmap='jet')

        if save_file is None and save_result_file is None:
            plt.show()

        plt.close(self.fig)

    def main_onclick(self, event):
        if isinstance(event.ydata, float) and isinstance(event.xdata, float):
            r, c = round(event.ydata), round(event.xdata)
        else:
            return

        if self.save_detail is not None:
            r, c = self.save_detail['pixel']

        self.r = r
        self.c = c

        for ax in self.fig.axes:
            ax.remove()
        self.fig.subplots(3, 3)

        ax = self.fig.axes[0]
        ax.set_title('Left Image', fontsize=self.image_font_size[0])
        ax.title.set_position(self.title_position)
        ax.axis('off')

        # Another method for ax.axis('off')
        # ax.set_xticks([])
        # ax.set_yticks([])

        # Change axis's font size
        # ax.tick_params(axis='x', labelsize=self.image_font_size[1])
        # ax.tick_params(axis='y', labelsize=self.image_font_size[1])
        ax.imshow(self.X[:, :, 0:3])
        ax.plot(c, r, 'r.', markersize=self.marker_size)

        ax = self.fig.axes[1]
        ax.set_title('Right Image', fontsize=self.image_font_size[0])
        ax.title.set_position(self.title_position)
        ax.axis('off')
        ax.imshow(self.X[:, :, 3:6])
        col_range = (c - self.max_disparity, c)
        row_range = (r, r)
        ax.plot(col_range, row_range, '--', color='#f2711c', linewidth=3)
        xlim = (col_range[0] - self.padding, col_range[1] + self.padding)
        ylim = (row_range[0] + self.padding, row_range[1] - self.padding)

        d = self.predict[r, c]
        ax.plot(c - d, r, color='blue', marker='.', markersize=self.marker_size)

        yd = self.Y[r, c]
        ax.plot(c - yd, r, color='red', marker='.', markersize=self.marker_size)

        ax = self.fig.axes[2]
        ax.set_title('Left Zoom Image', fontsize=self.image_font_size[0])
        ax.title.set_position(self.title_position)
        ax.axis('off')
        ax.imshow(self.X[:, :, 0:3])
        ax.plot(c, r, color='red', marker='.', markersize=self.marker_size)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)

        ax = self.fig.axes[3]
        ax.set_title('Right Zoom Image', fontsize=self.image_font_size[0])
        ax.title.set_position(self.title_position)
        ax.axis('off')
        ax.imshow(self.X[:, :, 3:6])
        ax.plot(col_range, row_range, '--', color='#f2711c', linewidth=3)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)

        d = self.predict[r, c]
        ax.plot(c - d, r, color='blue', marker='.', markersize=self.marker_size)

        yd = self.Y[r, c]
        ax.plot(c - yd, r, color='red', marker='.', markersize=self.marker_size)

        ax = self.fig.axes[4]
        ax.set_title(f'Ground Truth Disparity {self.Y[r, c]:.2f}', fontsize=self.image_font_size[0])
        ax.title.set_position(self.title_position)
        if 'KITTI' in self.dataset_name:
            self.Y[(self.Y == 0) | (self.error_map < 3)] = 0
        ax.imshow(self.Y, vmin=self.vmin, vmax=self.vmax, cmap='jet')
        ax.axis('off')
        ax.plot(c, r, color='red', marker='.', markersize=self.marker_size)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        # ax.set_xlim(c - 5, c + 5)  # height = 2 * padding
        # ax.set_ylim(r + 5, r - 5)  # width = 2 * padding

        if self.predict is not None:
            ax = self.fig.axes[5]
            ax.set_title(f'Predict Disparity {self.predict[r, c]:.2f}\n(avg EPE = {self.eval_dict["epe_loss"]:.3f})',
                         fontsize=self.image_font_size[0])
            ax.title.set_position(self.title_position)
            ax.imshow(self.predict, vmin=self.vmin, vmax=self.vmax, cmap='jet')
            ax.axis('off')
            ax.plot(c, r, color='red', marker='.', markersize=self.marker_size)
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)

        if self.error_map is not None:
            ax = self.fig.axes[6]
            if 'KITTI' in self.dataset_name:
                self.error_map[(self.Y == 0) | (self.error_map < 3)] = 0
            ax.set_title(f'Error Map {self.error_map[r, c]:.3f}', fontsize=self.image_font_size[0])
            ax.title.set_position(self.title_position)
            ax.imshow(self.error_map, cmap='jet')
            ax.axis('off')
            ax.plot(c, r, color='red', marker='.', markersize=self.marker_size)

        if self.confidence_error is not None:
            ax = self.fig.axes[7]
            ax.set_title(
                f'Confidence Error {self.confidence_error[r, c]:.2f}\n(avg CE = {self.eval_dict["CE_avg"]:.3f})',
                fontsize=self.image_font_size[0])
            ax.title.set_position(self.title_position)
            ax.imshow(self.confidence_error, cmap='jet')
            ax.axis('off')
            ax.plot(c, r, color='red', marker='.', markersize=self.marker_size)

        if self.candidate_error is not None:
            ax = self.fig.axes[8]
            ax.set_title(f'Candidate Error {self.candidate_error[r, c]:.2f}', fontsize=self.image_font_size[0])
            ax.title.set_position(self.title_position)
            ax.imshow(self.candidate_error, cmap='jet')
            ax.axis('off')
            ax.plot(c, r, color='red', marker='.', markersize=self.marker_size)

        # Templerary
        # ax = self.fig.axes[9]
        # ax.imshow(np.zeros(self.candidate_error.shape), cmap='jet')
        # ax.axis('off')
        # ax.plot(c, r, color='red', marker='.', markersize=self.marker_size)

        self.fig.tight_layout()
        self.fig.canvas.draw_idle()

        if self.save_detail is not None:
            folder = os.path.join(self.RESULT_ROOT, 'lr_check', self.save_detail['name'], f'{r}_{c}')
            os.makedirs(folder, exist_ok=True)
            # plt.imsave(os.path.join(folder, 'left.png'), self.X[:, :, 0:3])
            # plt.imsave(os.path.join(folder, 'right.png'), self.X[:, :, 3:6])
            # plt.imsave(os.path.join(folder, 'left_zoom.png'), self.X[ylim[0]:ylim[1], xlim[0]:xlim[1], 0:3])
            # plt.imsave(os.path.join(folder, 'right_zoom.png'), self.X[ylim[0]:ylim[1], xlim[0]:xlim[1], 3:6])
            # plt.imsave(os.path.join(folder, 'ground_truth.png'), self.Y, vmin=self.vmin, vmax=self.vmax, cmap='jet')
            # plt.imsave(os.path.join(folder, 'prediction.png'), self.predict, vmin=self.vmin, vmax=self.vmax, cmap='jet')
            # plt.imsave(os.path.join(folder, 'error_map.png'), self.error_map, vmin=self.vmin, vmax=self.vmax, cmap='jet')
            # plt.imsave(os.path.join(folder, 'confidence_error.png'), self.confidence_error, cmap='jet')
            self.fig.savefig(os.path.join(folder, 'detail.pdf'))

        self.plot_cost_volume(r, c)

    def plot_cost_volume(self, r, c, save_file=None):
        print(f'click: row = {r}, column = {c}')

        if self.cost_volume_fig is None:
            self.cost_volume_fig = plt.figure(figsize=(19.2, 12))
            self.cost_volume_fig.patch.set_alpha(0)
            self.cost_volume_fig.canvas.mpl_connect('button_press_event', self.cost_volume_onclick)
        else:
            for ax in self.cost_volume_fig.axes:
                ax.remove()

        self.cost_volume_fig.subplots(1)
        ax = self.cost_volume_fig.axes[0]
        ax.axvline(self.Y[r, c], color='k', linestyle='', marker='d', clip_on=False, markersize=self.marker_size,
                   label=f'Ground Truth Disparity ({self.Y[r, c]:.2f}, {self.confidence_error[r, c]:.2f})')

        for cv_data in self.cost_volume_data:
            p = ax.plot(cv_data.cost[:, r, c],
                        linestyle=cv_data.line_style,
                        linewidth=cv_data.line_width,
                        marker=cv_data.marker,
                        color=cv_data.color,
                        label=f'{cv_data.name} Cost')

            if cv_data.disp is not None:
                # p[0].get_color()
                ax.axvline(cv_data.disp[r, c], color='k', linestyle='--', clip_on=False,
                           linewidth=5, label=f'Predicted Disparity ({cv_data.disp[r, c]:.2f}, '
                                              f'{self.confidence_error[r, c]:.2f})')

        ax.set_xlabel('Disparity', fontsize=self.cv_font_size[0])
        ax.set_ylabel('Cost', fontsize=self.cv_font_size[0])
        ax.tick_params(axis='x', labelsize=self.cv_font_size[2], pad=15)
        ax.tick_params(axis='y', labelsize=self.cv_font_size[2])
        ax.legend(prop={'size': self.cv_font_size[1]})

        self.cost_volume_fig.tight_layout()
        self.cost_volume_fig.canvas.draw_idle()

        if self.save_detail is not None:
            folder = os.path.join(self.RESULT_ROOT, 'lr_check', self.save_detail['name'], f'{r}_{c}')
            self.cost_volume_fig.savefig(os.path.join(folder, 'cv.png'))

        if save_file is None:
            plt.show()
        else:
            plt.savefig(save_file, box_inches='tight')

    def cost_volume_onclick(self, event):
        d = round(event.xdata)

        if self.check_line is not None:
            self.check_line['main'][0].remove()
            self.check_line['cost_volume'].remove()

        self.check_line = {}

        ax = self.fig.axes[3]
        self.check_line['main'] = ax.plot(self.c - d, self.r, color='#21ba45', marker='.',
                                          markersize=self.marker_size, linewidth=5)

        ax = self.cost_volume_fig.axes[0]
        if self.confidence_error_cost is None:
            self.check_line['cost_volume'] = ax.axvline(d, color='#21ba45', linestyle='-', label=f'check disp ({d:.2f})')
        else:
            self.check_line['cost_volume'] = ax.axvline(d, color='#21ba45', linestyle='-',
                                                        label=f'check disp ({d:.2f}, '
                                                              f'{self.confidence_error_cost[d, self.r, self.c]:.2f})')
        ax.legend()

        self.fig.canvas.draw_idle()
        self.cost_volume_fig.canvas.draw_idle()


def save_comparision(X, Y, ganet_disp, sgm_disp, ganet_loss, sgm_loss, root, filename, model_name):
    assert isinstance(X, torch.Tensor)
    assert isinstance(Y, torch.Tensor)
    assert isinstance(ganet_disp, torch.Tensor)
    assert isinstance(sgm_disp, torch.Tensor)

    # Plot figures
    X = (X * 255).data.cpu().numpy().astype('uint8')
    X = X.swapaxes(1, 2).swapaxes(0, 2)
    Y = Y.data.cpu().numpy()
    ganet_disp = ganet_disp.data.cpu().numpy()
    sgm_disp = sgm_disp.data.cpu().numpy()

    fig = plt.figure(figsize=(19.2, 10.8))
    plt.subplot(231)
    plt.title('Left Image')
    plt.imshow(X[:, :, 0:3])

    plt.subplot(232)
    plt.title('Right Image')
    plt.imshow(X[:, :, 3:6])

    vmin = Y.reshape(-1).min()
    vmax = Y.reshape(-1).max()

    plt.subplot(234)
    plt.title('Ground True Disparity')
    plt.imshow(Y, vmin=vmin, vmax=vmax)

    plt.subplot(235)
    plt.title('{} [EPE = {:.3f}]'.format(model_name, ganet_loss))
    plt.imshow(ganet_disp, vmin=vmin, vmax=vmax)

    plt.subplot(236)
    plt.title('SGM [EPE = {:.3f}]'.format(sgm_loss))
    plt.imshow(sgm_disp, vmin=vmin, vmax=vmax)

    if ganet_loss < sgm_loss:
        subfolder = 'model-better'
    else:
        subfolder = 'sgm-better'

    os.makedirs(os.path.join(root, 'model-better'), exist_ok=True)
    os.makedirs(os.path.join(root, 'sgm-better'), exist_ok=True)

    # plt.show()
    plt.savefig(os.path.join(root, subfolder, filename), box_inches='tight')
    plt.close(fig)


def get_latest_version(file_path):
    version_codes = [version_code(x) for x in os.listdir(file_path)]
    if len(version_codes) > 1:
        version_codes.sort()
        return version_codes[-1]
    else:
        return None


class SGM:
    def __init__(self, block_size=5, max_disparity=192, mode=cv2.STEREO_SGBM_MODE_SGBM):
        P1 = int(8 * 3 * block_size * block_size)
        P2 = int(32 * 3 * block_size * block_size)
        self.max_disparity = max_disparity

        self.sgbm = cv2.StereoSGBM.create(0, max_disparity, block_size, P1=P1, P2=P2, mode=mode, disp12MaxDiff=1)

    def process(self, X, max_disparity_diff=1):
        X = (X * 255).data.cpu().numpy().astype('uint8')
        X = X.swapaxes(2, 3).swapaxes(1, 3)
        disps = []

        for i in range(X.shape[0]):
            disp_left = self.sgbm.compute(X[i, :, :, 0:3], X[i, :, :, 3:6])
            # disp_right = self.sgbm.compute(X[i, :, ::-1, 3:6], X[i, :, ::-1, 0:3])
            # disp_right = disp_right[:, ::-1]

            disp_left = torch.tensor(disp_left / 16).unsqueeze(0)
            # disp_right = torch.tensor(disp_right / 16).unsqueeze(0)
            disps.append(disp_left)

        disps = torch.cat(disps, dim=0)
        return disps.cuda()


def EPE_loss(input, target):
    return (input - target).abs().mean()


def error_rate(input, target, dataset_name):
    if dataset_name == 'flyingthings3D':
        error_mask = (input - target).abs() >= 1
        return error_mask.float().sum()

    elif dataset_name in ['KITTI_2015', 'KITTI_2015_benchmark', 'KITTI_2015_Augmentation', 'KITTI_2012_Augmentation']:
        l1 = (input - target).abs()
        error_mask = l1 >= 3
        error_mask &= (l1 / target.abs()) >= 0.05
        return error_mask.float().sum()

    elif dataset_name == 'AerialImagery':
        error_mask = (input - target).abs() >= 1
        return error_mask.float().sum()

    else:
        raise Exception('Unknown dataset: ' + dataset_name)


def error_rate_candidate(input, target, dataset_name, mask):
    target = target[mask]
    if dataset_name == 'flyingthings3D':
        error_mask = torch.ones(target.size(), dtype=torch.bool).to(input.device)
        for i in range(input.size(1)):
            error_mask &= (input[:, i][mask] - target).abs() >= 1
        return error_mask.float().sum()

    elif dataset_name == 'KITTI_2015':
        error_mask = torch.ones(target.size(), dtype=torch.bool).to(input.device)
        for i in range(input.size(1)):
            l1 = (input[:, i][mask] - target).abs()
            error_mask &= l1 >= 3
            error_mask &= (l1 / target.abs()) >= 0.05
        return error_mask.float().sum()


def rgb2bgr(x):
    y = np.zeros(x.shape, dtype=np.uint8)
    y[..., 0], y[..., 1], y[..., 2] = x[..., 2], x[..., 1], x[..., 0]
    return y


def threshold_color(loss):
    if loss >= 10:
        return Fore.RED
    elif loss >= 5:
        return Fore.YELLOW
    elif loss >= 1:
        return Fore.BLUE
    elif loss >= 0.5:
        return Fore.CYAN
    else:
        return Fore.GREEN


def y_mask(Y, max_disparity, dataset_name):
    mask = (Y < max_disparity - 1) & (Y != 0)
    if 'KITTI' in dataset_name:
        mask = mask & (Y != 0)
    return mask


def timespan_str(timespan):
    total = timespan.seconds
    second = total % 60 + timespan.microseconds / 1e+06
    total //= 60
    minute = int(total % 60)
    total //= 60
    return f'{minute:02d}:{second:05.2f}'


def flip_X(X, Y):
    flip_x = X[:, 0:3, :, :].data.cpu().numpy()
    flip_y = X[:, 3:6, :, :].data.cpu().numpy()
    flip_x = torch.tensor(flip_x[..., ::-1].copy())
    flip_y = torch.tensor(flip_y[..., ::-1].copy())

    X = torch.cat([flip_y, flip_x], dim=1).cuda()

    flip_d = Y.data.cpu().numpy()
    flip_d = torch.tensor(flip_d[:, ::-1, :, ::-1].copy())
    Y = flip_d.cuda()

    return X, Y


def trend_regression(loss_trend, method='corr'):
    """Loss descent checking"""
    if method == 'regression':
        b = loss_trend.reshape(-1, 1)  # b: (n, 1)
        A = np.concatenate([np.arange(len(b)).reshape(-1, 1), np.ones((len(b), 1))], axis=1)
        x = np.linalg.inv(A.T.dot(A)).dot(A.T).dot(b)
        return float(x[0, 0])

    elif method == 'corr':
        A = loss_trend
        B = np.arange(len(A))
        corr = np.corrcoef(A, B)[0, 1]
        return corr

    else:
        raise Exception(f'Method "{method}" is not valid')
