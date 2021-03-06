import numpy as np
import os
import tensorflow as tf
import threading
from datetime import datetime as dt

class CnnPredictor(object):
    """
    This predictor serves as an alternative approach to predict the classes in case we
    need to load the trained result only once, and perform prediction multiple times.
    """
    def __init__(self, session, model_scope, result_dir, result_file, k=1):
        """
        Args:
            model_scope: The variable_scope used for the trained model to be restored.
            session: The TensorFlow session used to run the prediction.
            result_dir: The full path to the folder in which the result file locates.
            result_file: The file that saves the training results.
            k: Optional. Number of elements to be predicted.
        """
        tf.train.import_meta_graph(os.path.join(result_dir, result_file + ".meta"))
        all_vars = tf.global_variables()
        model_vars = [var for var in all_vars if var.name.startswith(model_scope)]
        saver = tf.train.Saver(model_vars)
        saver.restore(session, os.path.join(result_dir, result_file))

        # Retrieve the Ops we 'remembered'.
        logits = tf.get_collection(model_scope+"logits")[0]
        self.images_placeholder = tf.get_collection(model_scope+"images")[0]
        self.keep_prob_placeholder = tf.get_collection(model_scope+"keep_prob")[0]

        # Add an Op that chooses the top k predictions. Apply softmax so that
        # we can have the probabilities (percentage) in the output.
        self.eval_op = tf.nn.top_k(tf.nn.softmax(logits), k=k)
        self.session = session

    def predict(self, img_features, limit=10000):
        """
        Args:
            img_features: A 2-D ndarray (matrix) each row of which holds the pixels as
                features of one image. One or more rows (image samples) can be requested
                to be predicted at once.
            limit: Optional. This specifies the limit of images that can be processed at
                once due to the limitation of the GPU/CPU memory. Adjust this based on 
                the capacity of the device, the image size, and the model size.
        Returns:
            values and indices. Refer to tf.nn.top_k for details.
        """
        feat_cnt, _ = img_features.shape
        if feat_cnt <= limit:
            pred = self.session.run(self.eval_op,
                                    feed_dict={self.images_placeholder: img_features,
                                               self.keep_prob_placeholder: 1.0})
            return pred.values, pred.indices
        else:
            vals_list, inds_list = [], []
            feat_index = 0
            for i in range(0, feat_cnt, limit):
                si, ei = i, i + limit
                this_part = img_features[si:ei, :]
                vals, inds = self.session.run(self.eval_op,
                                              feed_dict={self.images_placeholder: this_part,
                                                         self.keep_prob_placeholder: 1.0})
                vals_list.extend(vals)
                inds_list.extend(inds)
                feat_index = ei

            if feat_index < feat_cnt:
                this_part = img_features[feat_index:, :]
                vals, inds = self.session.run(self.eval_op,
                                              feed_dict={self.images_placeholder: this_part,
                                                         self.keep_prob_placeholder: 1.0})
                vals_list.extend(vals)
                inds_list.extend(inds)

            values, indices = np.asarray(vals_list), np.asarray(inds_list)
            assert values.shape[0] == feat_cnt and indices.shape[0] == feat_cnt

            return values, indices

def get_all_models(model_dir, prefix):
    """
    Args:
        model_dir: The name of the full path folder in which the model training results 
            were saved.
        prefix: The prefix of the file name in lower case, such as step1_.
    Returns: A python list containing the file names (excluding the path name, and the 
        suffix) of all trained models.
    """
    model_list = []
    for model_file in os.listdir(model_dir):
        full_path_name = os.path.join(model_dir, model_file)
        if os.path.isfile(full_path_name) and model_file.lower().startswith(prefix) \
                and model_file.lower().endswith('.meta'):
            model_list.append(model_file[:-5])

    return model_list