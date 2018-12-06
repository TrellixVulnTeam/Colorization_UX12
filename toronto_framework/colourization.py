"""
Colourization of CIFAR-10 Horses via classification.
"""

from __future__ import print_function
import argparse
import os
import math
import numpy as np
import numpy.random as npr
import scipy.misc
import time
import torch 
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
import matplotlib
matplotlib.use('Agg') # switch backend
import matplotlib.pyplot as plt 


from load_data import load_cifar10
from preprocessing import *
from models import *
import unet
import generator_copy


HORSE_CATEGORY = 7


######################################################################
# Torch Helper
######################################################################

def get_torch_vars(xs, ys, gpu=False):
	"""
	Helper function to convert numpy arrays to pytorch tensors.
	If GPU is used, move the tensors to GPU.

	Args:
	  xs (float numpy tenosor): greyscale input
	  ys (int numpy tenosor): categorical labels 
	  gpu (bool): whether to move pytorch tensor to GPU
	Returns:
	  Variable(xs), Variable(ys)
	"""
	xs = torch.from_numpy(xs).float()
	ys = torch.from_numpy(ys).float()
	# ys = torch.from_numpy(ys).long()
	if gpu:
		# xs = xs.cuda()
		# ys = ys.cuda()
		xs = torch.tensor(xs, device=device)
		ys = torch.tensor(ys, device = device)
	return Variable(xs), Variable(ys)

def compute_loss(criterion, outputs, labels, batch_size, num_colours):
	"""
	Helper function to compute the loss. Since this is a pixelwise
	prediction task we need to reshape the output and ground truth
	tensors into a 2D tensor before passing it in to the loss criteron.

	Args:
	  criterion: pytorch loss criterion
	  outputs (pytorch tensor): predicted labels from the model
	  labels (pytorch tensor): ground truth labels
	  batch_size (int): batch size used for training
	  num_colours (int): number of colour categories
	Returns:
	  pytorch tensor for loss
	"""

	loss_out = outputs.transpose(1,3) \
					  .contiguous() \
					  .view([batch_size*32*32, num_colours])
	loss_lab = labels.transpose(1,3) \
					  .contiguous() \
					  .view([batch_size*32*32])
	return criterion(loss_out, loss_lab)

def run_validation_step(cnn, criterion, x_test_lab, y_test_lab, batch_size,
						colour, plotpath=None):
	correct = 0.0
	total = 0.0
	losses = []
	for i, (xs, ys) in enumerate(get_batch(x_test_lab, y_test_lab, batch_size)):
		images, labels = get_torch_vars(xs, ys, gpu)
		outputs = cnn(images)
		# outputs = cnn.forward(images, mode='colorization')

		# val_loss = compute_loss(criterion,
		# 						outputs,
		# 						labels,
		# 						batch_size=batch_size,
		# 						num_colours=num_colours)
		val_loss = criterion(outputs,labels)
		losses.append(val_loss.data[0])

		# _, predicted = torch.max(outputs.data, 1, keepdim=True)
		# total += labels.size(0) * 32 * 32
		# correct += (predicted == labels.data).sum()

	if plotpath: # only plot if a path is provided
		plot_lab(xs, ys, outputs.detach().cpu().numpy(), plotpath)
	val_loss = np.mean(losses)
	val_acc = 0
	# val_acc = 100 * correct / total
	return val_loss, val_acc


######################################################################
# MAIN
######################################################################

if __name__ == '__main__':
	'''
	parser = argparse.ArgumentParser(description="Train colourization")
	parser.add_argument('--gpu', action='store_true', default=False,
						help="Use GPU for training")
	parser.add_argument('--valid', action="store_true", default=False,
						help="Perform validation only (don't train)")
	parser.add_argument('--checkpoint', default="",
						help="Model file to load and save")
	parser.add_argument('--plot', action="store_true", default=False,
						help="Plot outputs every epoch during training")
	parser.add_argument('-c', '--colours',
						default='colours/colour_kmeans24_cat7.npy',
						help="Discrete colour clusters to use")
	parser.add_argument('-m', '--model', choices=["CNN", "UNet", "DUNet"],
						help="Model to run")
	parser.add_argument('-k', '--kernel', default=3, type=int,
						help="Convolution kernel size")
	parser.add_argument('-f', '--num_filters', default=32, type=int,
						help="Base number of convolution filters")
	parser.add_argument('-l', '--learn_rate', default=0.001, type=float,
						help="Learning rate")
	parser.add_argument('-b', '--batch_size', default=100, type=int,
						help="Batch size")
	parser.add_argument('-e', '--epochs', default=25, type=int,
						help="Number of epochs to train")
	parser.add_argument('-s', '--seed', default=0, type=int,
						help="Numpy random seed")

	args = parser.parse_args()
	'''

	# Set the maximum number of threads to prevent crash in Teaching Labs
	torch.set_num_threads(5)
	
	# SET ARGUMENTS
	experiment = "Unet_256_animals"
	model = "UNet" # "CNN", "DUNet", "UNet"
	batch_size = 100
	plot_images = True
	n_epochs = 50
	save_model = True
	model_path = os.path.join("./models", experiment)
	if not os.path.exists(model_path):
		os.makedirs(model_path)
	validation = False # inference
	gpu = True
	if gpu:
		device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
	else:
		device = "cpu"
	print(device)
	num_filters = 128 
	kernel_size = 3
	lr = 0.001
	seed = 0

	# Create the outputs folder if not created already
	if not os.path.exists(os.path.join("./outputs",experiment)):
		os.makedirs(os.path.join("./outputs",experiment))
	# Numpy random seed
	npr.seed(seed)

	# LOAD THE COLOURS CATEGORIES
	# colours = np.load(args.colours)[0]
	colours = np.load('colours/colour_kmeans24_cat7.npy')[0]
	# num_colours = np.shape(colours)[0]
	num_colours = 2

	# LOAD THE MODEL
	'''
	if model == "CNN":
		cnn = CNN(kernel_size, num_filters, num_colours)
	elif model == "UNet":
		cnn = UNet(kernel_size, num_filters, num_colours)
	else: # model == "DUNet":
		cnn = DilatedUNet(kernel_size, num_filters, num_colours)
	'''
	cnn = unet.UNet(n_channels=1, n_classes=2)
	# cnn = generator_copy.unet()
	print(cnn)

	# LOSS FUNCTION
	# criterion = nn.CrossEntropyLoss()
	criterion = nn.L1Loss()
	optimizer = torch.optim.Adam(cnn.parameters(), lr=lr)

	# DATA
	print("Loading data...")
	(x_train, y_train), (x_test, y_test) = load_cifar10()

	print("Transforming data...")
	x_train_lab, y_train_lab = process_lab(x_train, y_train, categories=[bird, horse, cat, deer])
	print(x_train_lab.shape)
	print(y_train_lab.shape)
	# train_rgb, train_grey = process(x_train, y_train)
	# train_rgb_cat = get_rgb_cat(train_rgb, colours)
	x_test_lab, y_test_lab = process_lab(x_test, y_test,categories=[bird, horse, cat, deer])
	# test_rgb, test_grey = process(x_test, y_test)
	# test_rgb_cat = get_rgb_cat(test_rgb, colours)
	
	

	# Run validation only
	# if args.valid:
	
	'''
	if validation:
		if not save_model:
			raise ValueError("You need to give trained model to evaluate")

		print("Loading checkpoint...")
		cnn.load_state_dict(torch.load(args.checkpoint, map_location=lambda storage, loc: storage))
		img_path = "outputs/eval_%s.png" % args.model
		val_loss, val_acc = run_validation_step(cnn,
												criterion,
												test_grey,
												test_rgb_cat,
												args.batch_size,
												colours,
												img_path)
		print('Evaluating Model %s: %s' % (args.model, args.checkpoint))
		print('Val Loss: %.4f, Val Acc: %.1f%%' % (val_loss, val_acc))
		print('Sample output available at: %s' % img_path)
		exit(0)
	'''
	
	print("Beginning training ...")

	# if args.gpu: cnn.cuda()
	device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
	cnn.to(device)
	start = time.time()

	train_losses = []
	valid_losses = []
	valid_accs = []
	# for epoch in range(args.epochs):
	for epoch in range(n_epochs):
		# Train the Model
		cnn.train() # Change model to 'train' mode
		losses = []
		# for i, (xs, ys) in enumerate(get_batch(train_grey,
		#                                        train_rgb_cat,
		#                                        args.batch_size)):
		for i, (xs, ys) in enumerate(get_batch(x_train_lab,
											   y_train_lab,
											   batch_size)):
			# images, labels = get_torch_vars(xs, ys, args.gpu)
			images, labels = get_torch_vars(xs,ys, True)
			# Forward + Backward + Optimize
			optimizer.zero_grad()
			outputs = cnn(images)
			# outputs = cnn.forward(images, mode='colorization')

			# loss = compute_loss(criterion,
			# 					outputs,
			# 					labels,
			# 					batch_size=batch_size,
			# 					num_colours=num_colours)
			loss = criterion(outputs,labels)
			# labels = labels.type(torch.cuda.FloatTensor)
			# loss = criterion(outputs, labels)
			loss.backward()
			optimizer.step()
			losses.append(loss.data[0])

		# plot training images
		# if args.plot:
		if plot_images:
			# _, predicted = torch.max(outputs.data, 1, keepdim=True)
			# plot(xs, ys, predicted.cpu().numpy(), colours,
			# 	 'outputs/train_%d.png' % epoch)
			plot_lab(xs, ys, outputs.detach().cpu().numpy(),
				 'outputs/train_%d.png' % epoch)

		
		# plot training images
		avg_loss = np.mean(losses)
		train_losses.append(avg_loss)
		time_elapsed = time.time() - start
		print('Epoch [%d/%d], Loss: %.4f, Time (s): %d' % (
			epoch+1, n_epochs, avg_loss, time_elapsed))

		# Evaluate the model
		cnn.eval()  # Change model to 'eval' mode (BN uses moving mean/var).

		outfile = None
		# if args.plot:
		if plot_images:
			outfile = 'outputs/test_%d.png' % epoch

		val_loss, val_acc = run_validation_step(cnn,
												criterion,
												x_test_lab,
												y_test_lab,
												batch_size,
												colours,
												outfile)

		time_elapsed = time.time() - start
		valid_losses.append(val_loss)
		valid_accs.append(val_acc)
		print('Epoch [%d/%d], Val Loss: %.4f, Val Acc: %.1f%%, Time(s): %d' % (
			epoch+1, n_epochs, val_loss, val_acc, time_elapsed))
		
		if save_model:
			if epoch%5 == 0:
				print('Saving model...')
				torch.save(cnn.state_dict(), os.path.join(model_path,'model'+str(epoch)+'.weights'))

	# Plot training curve
	plt.plot(train_losses, "ro-", label="Train")
	plt.plot(valid_losses, "go-", label="Validation")
	plt.legend()
	plt.title("Loss")
	plt.xlabel("Epochs")
	plt.savefig("outputs/training_curve.png")
	plt.close()
	# plt.clf()

	# if args.checkpoint:
	if save_model:
		print('Saving model...')
		torch.save(cnn.state_dict(), os.path.join(model_path,'model.weights'))
	
	