from keras.models import Sequential
from keras.layers import Dense, Dropout, Conv2D, Flatten, Activation, MaxPooling2D, BatchNormalization
import keras
import keras.backend as K
import numpy as np
import sys, glob, argparse


NX, NY = 64, 64
WINDOWS_PER_IMAGE = 32
#variables = ["dens", "temp", "pres"]
variables = ["dens"]


class FlashDatasetGenerator(keras.utils.Sequence):
    def __init__(self, data_dir, batch_size):
        clean_files = glob.glob(data_dir+"/0/clean/*.npy*")
        error_files = glob.glob(data_dir+"/0/error/*.npy*")
        self.files = clean_files + error_files
        self.clean_labels, self.error_labels = len(clean_files), len(error_files)
        self.labels = np.append(np.zeros(self.clean_labels), np.ones(self.error_labels))
        self.batch_size = batch_size

    def __len__(self):
        return np.ceil(len(self.files) / float(self.batch_size))

    def __getitem__(self, idx):
        batch_x = self.files[idx*self.batch_size: (idx+1)*self.batch_size]
        batch_y = self.labels[idx*self.batch_size: (idx+1)*self.batch_size]
        data = []
        for filename in batch_x:
            if ".npy" in filename:
                img = np.load(filename)[:,:,0:1]
            if ".dat" in filename:
                img = np.fromfile(filename).reshape(NX, NY, len(variables))
            data.append(img)
        return np.array(data), batch_y

    def get_true_labels(self):
        truth = [0] * (self.clean_labels/WINDOWS_PER_IMAGE) + [1] * (self.error_labels/WINDOWS_PER_IMAGE)
        return np.array(truth)

model = Sequential([
    Conv2D(64, (3,3), input_shape=(NX, NY, len(variables))),
    #BatchNormalization(),
    MaxPooling2D(pool_size=(3, 3)),
    Activation('relu'),
    #Dropout(0.25),
    Conv2D(64, (3,3), activation='relu'),
    MaxPooling2D(pool_size=(3, 3)),
    Conv2D(32, (3,3), activation='relu'),
    MaxPooling2D(pool_size=(3, 3)),

    Flatten(),
    #Dense(256, activation='relu'),
    #Dropout(0.5),
    Dense(1, activation='sigmoid')
])

model.compile(optimizer='adam',
              loss='binary_crossentropy',
              metrics=['accuracy'])

def compute_metrics(pred_labels, true_labels):
    clean_samples = np.sum(true_labels == 0) * 1.0
    error_samples = np.sum(true_labels == 1) * 1.0
    total = clean_samples + error_samples * 1.0
    # True Positive (TP): we predict a label of 1 (positive), and the true label is 1.
    tp = np.sum(np.logical_and(pred_labels == 1, true_labels == 1))
    # True Negative (TN): we predict a label of 0 (negative), and the true label is 0.
    tn = np.sum(np.logical_and(pred_labels == 0, true_labels == 0))
    # False Positive (FP): we predict a label of 1 (positive), but the true label is 0.
    fp = np.sum(np.logical_and(pred_labels == 1, true_labels == 0))
    # False Negative (FN): we predict a label of 0 (negative), but the true label is 1.
    fn = np.sum(np.logical_and(pred_labels == 0, true_labels == 1))
    recall, fpr = tp / error_samples, fp / total
    accuracy = (tp + tn) / total
    print 'TP: %s (%i/%i), FP: %s (%i/%i)' %(recall, tp, error_samples, fpr, fp, total)
    print 'ACC: %s, TN: %i, FN: %i' %(accuracy, tn, fn)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--train_dataset", help="The path to the training set")
    parser.add_argument("-e", "--test_dataset", help="The path to the test set")
    args = parser.parse_args()

    if args.train_dataset:
        data_gen = FlashDatasetGenerator(args.train_dataset, 128)
        #model.load_weights('model_keras.h5')
        model.fit_generator(generator=data_gen, use_multiprocessing=True, workers=8, epochs=10)
        model.save_weights('model_keras.h5')
        print model.evaluate_generator(generator=data_gen, use_multiprocessing=True, workers=8, verbose=1)
    elif args.test_dataset:
        data_gen = FlashDatasetGenerator(args.test_dataset, 128)
        model.load_weights('model_keras.h5')
        scores = model.predict_generator(generator=data_gen, use_multiprocessing=True, workers=8, verbose=1)
        scores = scores.reshape((len(scores)/WINDOWS_PER_IMAGE, WINDOWS_PER_IMAGE))
        for threshold in [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]:
            print "Threshold =", threshold
            pred = (scores >= threshold)    # shape of (N, WINDOWS_PER_IMAGE)
            pred = np.any(pred, axis=1)
            compute_metrics(pred, data_gen.get_true_labels())
