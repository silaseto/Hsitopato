import sys
import os
from pathlib import Path
import numpy as np
import cv2
import tkinter as tk
import tkfilebrowser

from base import *
from UserProgress import UserProgress
from Images import Images
from TypeOneDetections import TypeOneDetections
from PredictionGrids import PredictionGrids
from BeginDialog import BeginDialog




class Dataset(object):
    # To store all our subdatasets throughout our pipeline and manage progress throughout pipeline

    def __init__(self, uid=None, restart=None, dialog=True):
        # Get uid if needed

        if dialog:
            # root = tk.Tk()
            # root.title("L.I.R.A.")
            # root.withdraw()
            begin_options = {}
            bd = BeginDialog(begin_options)

            if "uid" in begin_options and \
                "restart" in begin_options and \
                "model" in begin_options:

                uid = begin_options["uid"]
                restart = begin_options["restart"]
                self.model = begin_options["model"]

                print(uid, restart, self.model)

            else:
                sys.exit("Exiting...")

        if uid is not None:
            self.uid = uid
        else:
            self.uid = input("Input your Unique/User ID for this Dataset: ")

        # Initialize user progress to existing progress if it exists and default starting progress otherwise
        self.progress = UserProgress(self.uid, model=self.model)
        # Check whether to reload the imgs archive, and possibly restart our progress
        if restart is not None:
            self.restart = restart
        else:
            self.restart = input(
                "Would you like to reset your classification progress and restart from the beginning? (This will "
                "re-load all images) [Y\\N]: ").upper() == "Y "

        if self.restart:
            # User wants to restart, both imgs and progress
            self.imgs = Images(self.uid, restart=True)
            self.progress.restart(model=self.model)
            self.type_one_detections = TypeOneDetections(self, self.uid, restart=True)
            self.prediction_grids = PredictionGrids(self, self.uid, restart=True)

        else:
            # User does not want to restart. Defaults to this if they didn't put in "Y"
            if self.progress.editing_started():
                # If they were already editing these images, resume progress
                self.imgs = Images(self.uid, restart=False)
                self.type_one_detections = TypeOneDetections(self, self.uid, restart=False)
                self.prediction_grids = PredictionGrids(self, self.uid, restart=False)
            else:
                # If they weren't already editing these images (i.e. they haven't started editing), load the images.
                # No need to restart our progress since it's already the initial value.
                self.imgs = Images(self.uid, restart=True)
                self.type_one_detections = TypeOneDetections(self, self.uid, restart=True)
                self.prediction_grids = PredictionGrids(self, self.uid, restart=True)

    def detect_type_ones(self):
        # Detect type ones, suppress them, and allow human-in-the-loop editing. If our user progress indicates they
        # have already done some or all of these steps, we will skip over the already-completed steps.

        # Only generate if user hasn't started editing (meaning they already had them generated before)
        if not self.progress["type_ones_started_editing"]:
            self.type_one_detections.generate()

        # Only edit if the user hasn't finished editing
        if not self.progress["type_ones_finished_editing"] and not self.progress["model"] == "balbc":
            self.type_one_detections.edit()

    def predict_grids(self):
        # Detect all predictions and allow human-in-the-loop editing If our user progress indicates they have already
        # done some or all of these steps, we will skip over the already-completed steps.

        # Only generate if user hasn't started editing (meaning they already had them generated before)
        if not self.progress["prediction_grids_started_editing"]:
            self.prediction_grids.generate()

        # Only edit if the user hasn't finished editing
        if not self.progress["prediction_grids_finished_editing"]:
            self.prediction_grids.edit()

    def get_stats(self):
        # Once we're sure the user's session is complete:
        if self.progress["prediction_grids_finished_editing"]:


            outfile_name = tkfilebrowser.asksaveasfilename(
                title='Save output CSV file',
                defaultext=".csv",
                initialdir=os.path.join(str(Path.home()), 'Documents'),
                initialfile='{}_stats.csv'.format(self.uid),
                filetypes=[("CSV file", "*.csv")])
            # Generate a CSV with raw counts of each classification on each image,
            #   with the percentages each classification takes up of the image,
            #   not including empty slide,
            #   and the number of type one lesions detected on each image.
            with open(outfile_name, "w") as f:
                # Write Header line
                f.write("Image,Healthy Tissue,Type I - Caseum,Type II,Type III,Type I - Rim,Unknown/Misc,\
                        ,Healthy Tissue,Type I - Caseum,Type II,Type III,Type I - Rim,Unknown/Misc,\
                        ,Number of Type One Lesions\n")

                # Iterate through predictions and detections

                prediction_sums = []
                last_prediction_counts = None
                last_name = None
                last_detection_count = None
                for i, (prediction_grid, detections) in enumerate(
                        zip(self.prediction_grids.after_editing, self.type_one_detections.after_editing)):
                    sys.stdout.write("\rGenerating Stats on Image {}/{}...".format(i, len(self.imgs) - 1))

                    # Get counts of each classification type, excluding empty slide
                    prediction_counts = np.zeros((6))
                    classification_i = 0
                    for classification in range(7):
                        if classification != 3:
                            prediction_counts[classification_i] = np.sum(prediction_grid == classification)
                            classification_i += 1
                    if i == 0:
                        prediction_sums = prediction_counts
                    else:
                        for j, count in enumerate(prediction_counts):
                            prediction_sums[j] += count
                    # Get total number of classifications for this image
                    prediction_n = np.sum(prediction_counts)

                    # Get percentage each classification takes up of the total classifications
                    prediction_avgs = 100 * prediction_counts / prediction_n

                    # Get the number of Type One Lesions / Type One Detection Clusters in this image
                    detection_count = len(get_rect_clusters(detections))

                    # Write
                    full_name = self.imgs.fnames[i]
                    # if full_name.endswith("(1)"):
                    #     last_prediction_counts = prediction_counts
                    #     last_name = " ".join(full_name.split(" ")[:-1])
                    #     last_detection_count = detection_count
                    #     continue
                    # el
                    if full_name.endswith(")"):

                        current_name = " ".join(full_name.split(" ")[:-1])
                        if last_prediction_counts is None:
                            last_prediction_counts = prediction_counts
                            last_detection_count = detection_count
                            last_name = current_name
                        elif last_name == current_name:
                            for j in range(len(last_prediction_counts)):
                                last_prediction_counts[j] += prediction_counts[j]
                            last_detection_count += detection_count
                            detection_count = last_detection_count
                            prediction_counts = last_prediction_counts
                        if i + 1 < len(self.imgs.fnames):
                            next_name = " ".join(self.imgs.fnames[i + 1].split(" ")[:-1])
                            if next_name == current_name:
                                continue
                            else:
                                full_name = current_name
                                prediction_counts = last_prediction_counts
                                detection_count = last_detection_count
                                last_prediction_counts = None
                                last_name = None
                                last_detection_count = None
                        else:
                            full_name = current_name

                    f.write("{},{},,{},,{}\n".format(full_name, ",".join(map(str, list(prediction_counts))),
                                                     ",".join(map(str, list(prediction_avgs))), detection_count))


                detection_total = sum([len(get_rect_clusters(d)) for d in self.type_one_detections.after_editing])

                total = sum(prediction_sums)
                sum_average = [100 * p / total for p in prediction_sums]

                f.write("\nsummary,{},,{},,{}\n".format(",".join(map(str, list(prediction_sums))),
                                                        ",".join(map(str, list(sum_average))),
                                                        detection_total))

                sys.stdout.flush()
                print("")

            # Generate a displayable image of the predictions overlaid, for each image.
            resize_factor = 1 / 8
            color_key = [(255, 0, 255), (0, 0, 255), (0, 255, 0), (200, 200, 200), (0, 255, 255), (255, 0, 0),
                         (244, 66, 143)]
            alpha = 0.33
            for i, (img, prediction_grid) in enumerate(zip(self.imgs, self.prediction_grids.after_editing)):
                sys.stdout.write("\rGenerating Displayable Results for Image {}/{}...".format(i, len(self.imgs) - 1))

                # Since our image and predictions would be slightly misalgned from each other due to rounding,
                # We recompute the sub_h and sub_w and img resize factors to make them aligned.
                sub_h = int(resize_factor * self.prediction_grids.sub_h)
                sub_w = int(resize_factor * self.prediction_grids.sub_w)
                fy = (prediction_grid.shape[0] * sub_h) / img.shape[0]
                fx = (prediction_grid.shape[1] * sub_w) / img.shape[1]

                # Then resize the image with these new factors
                img = cv2.resize(img, (0, 0), fx=fx, fy=fy)

                # Make overlay to store prediction rectangles on before overlaying on top of image
                prediction_overlay = np.zeros_like(img)

                for row_i, row in enumerate(prediction_grid):
                    for col_i, col in enumerate(row):
                        color = color_key[col]
                        # draw rectangles of the resized sub_hxsub_w size on it
                        cv2.rectangle(prediction_overlay, (col_i * sub_w, row_i * sub_h),
                                      (col_i * sub_w + sub_w, row_i * sub_h + sub_h), color, -1)

                # Add overlay to image to get resulting image
                display_img = weighted_overlay(img, prediction_overlay, alpha)

                # Write img
                cv2.imwrite("../../Output Stats/{}_overlay_{}.png".format(self.uid, self.imgs.fnames[i]), display_img)

            sys.stdout.flush()
            print("")
