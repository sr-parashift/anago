import os

import numpy as np
from keras.callbacks import Callback, TensorBoard, EarlyStopping, ModelCheckpoint


def get_callbacks(log_dir=None, save_dir=None, valid=(), eary_stopping=True):
    callbacks = []

    if log_dir:
        if not os.path.exists(log_dir):
            print('Successfully made a directory: {}'.format(log_dir))
            os.mkdir(log_dir)
        callbacks.append(TensorBoard(log_dir))

    if valid:
        callbacks.append(F1score(*valid))

    if save_dir:
        if not os.path.exists(save_dir):
            print('Successfully made a directory: {}'.format(save_dir))
            os.mkdir(save_dir)

        file_name = '_'.join(['model_weights', '{epoch:02d}', '{f1:.2f}']) + '.h5'
        save_callback = ModelCheckpoint(os.path.join(save_dir, file_name),
                                        monitor='f1',
                                        save_weights_only=True)
        callbacks.append(save_callback)

    if eary_stopping:
        callbacks.append(EarlyStopping(monitor='f1'))

    return callbacks


def get_entities(seq):
    """
    Arguments:
        seq: ["B-PER", "I-PER", "O", "B-LOC", ...] sequence of labels
    Returns:
        list of (chunk_type, chunk_start, chunk_end)

    Example:
        seq: ["B-PER", "I-PER", "O", "B-LOC"]
        result = [("PER", 0, 2), ("LOC", 3, 4)]
    """
    i = 0
    chunks = []
    seq = seq + ['O']  # add sentinel
    types = [tag.split('-')[-1] for tag in seq]
    while i < len(seq):
        if seq[i].startswith('B'):
            for j in range(i+1, len(seq)):
                if seq[j].startswith('I') and types[j] == types[i]:
                    continue
                break
            chunks.append((types[i], i, j))
            i = j
        else:
            i += 1
    return chunks


def f1_score(y_true, y_pred, sequence_lengths):
    """
    Evaluates performance on test set
    Args:
        sess: tensorflow session
        test: dataset that yields tuple of sentences, tags
        tags: {tag: index} dictionary
    Returns:
        accuracy
        f1 score
    """
    correct_preds, total_correct, total_preds = 0., 0., 0.
    for lab, lab_pred, length in zip(y_true, y_pred, sequence_lengths):
        lab = lab[:length]
        lab_pred = lab_pred[:length]

        lab_chunks = set(get_entities(lab))
        lab_pred_chunks = set(get_entities(lab_pred))

        correct_preds += len(lab_chunks & lab_pred_chunks)
        total_preds += len(lab_pred_chunks)
        total_correct += len(lab_chunks)

    p = correct_preds / total_preds if correct_preds > 0 else 0
    r = correct_preds / total_correct if correct_preds > 0 else 0
    f1 = 2 * p * r / (p + r) if correct_preds > 0 else 0
    return f1


class F1score(Callback):
    def __init__(self, valid_steps, valid_batches, preprocessor=None, model=None):
        super(F1score, self).__init__()
        self.valid_steps = valid_steps
        self.valid_batches = valid_batches
        self.p = preprocessor
        self.model_ = model

    def on_epoch_end(self, epoch, logs={}):
        correct_preds, total_correct, total_preds = 0., 0., 0.
        for i, (data, label) in enumerate(self.valid_batches):
            if i == self.valid_steps:
                break
            y_true = label
            y_true = np.argmax(y_true, -1)
            sequence_lengths = np.argmin(y_true, -1)
            y_pred = np.asarray(self.model_.predict(data, sequence_lengths))

            y_pred = [self.p.inverse_transform(y[:l]) for y, l in zip(y_pred, sequence_lengths)]
            y_true = [self.p.inverse_transform(y[:l]) for y, l in zip(y_true, sequence_lengths)]

            a, b, c = self.count_correct_and_pred(y_true, y_pred, sequence_lengths)
            correct_preds += a
            total_preds += b
            total_correct += c

        f1 = self._calc_f1(correct_preds, total_correct, total_preds)
        print(' - f1: {:04.2f}'.format(f1 * 100))
        logs['f1'] = f1

    def _calc_f1(self, correct_preds, total_correct, total_preds):
        p = correct_preds / total_preds if correct_preds > 0 else 0
        r = correct_preds / total_correct if correct_preds > 0 else 0
        f1 = 2 * p * r / (p + r) if correct_preds > 0 else 0
        return f1

    def count_correct_and_pred(self, y_true, y_pred, sequence_lengths):
        correct_preds, total_correct, total_preds = 0., 0., 0.
        for lab, lab_pred, length in zip(y_true, y_pred, sequence_lengths):
            lab = lab[:length]
            lab_pred = lab_pred[:length]

            lab_chunks = set(get_entities(lab))
            lab_pred_chunks = set(get_entities(lab_pred))

            correct_preds += len(lab_chunks & lab_pred_chunks)
            total_preds += len(lab_pred_chunks)
            total_correct += len(lab_chunks)
        return correct_preds, total_correct, total_preds
