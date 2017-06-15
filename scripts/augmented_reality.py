#!/usr/bin/env python
"""OpenCV feature detectors with ros CompressedImage Topics in python.

This example subscribes to a ros topic containing sensor_msgs 
CompressedImage. It converts the CompressedImage into a numpy.ndarray, 
then detects and marks features in that image. It finally displays 
and publishes the new image - again as CompressedImage topic.
"""
__author__ =  'Simon Haller <simon.haller at uibk.ac.at>'
__version__=  '0.1'
__license__ = 'BSD'
# Python libs
import sys, time

# numpy and scipy
import numpy as np
from scipy.ndimage import filters

# OpenCV
import cv2

# Ros libraries
import roslib
import rospy

# Ros Messages
from sensor_msgs.msg import CompressedImage
# We do not use cv_bridge it does not support CompressedImage in python
# from cv_bridge import CvBridge, CvBridgeError

VERBOSE=False

# termination criteria
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

chessWidth = 4
chessHeight = 5

# prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
objp = np.zeros((chessWidth*chessHeight,3), np.float32)
objp[:,:2] = np.mgrid[0:chessHeight,0:chessWidth].T.reshape(-1,2)

# Size of the chess depends on segmentLenght
segmentLenght = 2
# 16 points of a 3*3 chessboard
#axis_points = [[0,0,0], [1,0,0], [2,0,0], [3,0,0], [0,1,0], [1,1,0], [2,1,0], [3,1,0], [0,2,0], [1,2,0], [2,2,0], [3,2,0], [0,3,0], [1,3,0], [2,3,0], [3,3,0]]
axis = np.float32( [[0,0,0], [3,0,0], [3,3,0], [0,3,0]] )


def _generatePlateCorners( imgpts ):
    imgpts = np.float32(imgpts).reshape(-1,2)

    coefInconnu = 0.9
    corners = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]

    corners[0] = imgpts[0]
    corners[1] = imgpts[1]
    corners[5] = imgpts[2]
    corners[4] = imgpts[3]

    dist01_x = ( imgpts[1][0] - imgpts[0][0] )
    dist01_y = ( imgpts[1][1] - imgpts[0][1] )
    dist12_x = coefInconnu * dist01_x
    dist12_y = coefInconnu * dist01_y
    corners[2] = ( int( corners[1][0] + dist12_x ), int( corners[1][1] + dist12_y ) )
    dist23_x = coefInconnu * dist12_x
    dist23_y = coefInconnu * dist12_y
    corners[3] = ( int( corners[2][0] + dist23_x ), int( corners[2][1] + dist23_y ) )

    dist04_x = ( imgpts[3][0] - imgpts[0][0] )
    dist04_y = ( imgpts[3][1] - imgpts[0][1] )
    dist48_x = coefInconnu * dist04_x
    dist48_y = coefInconnu * dist04_y
    corners[8] = ( int( corners[4][0] + dist48_x ), int( corners[4][1] + dist48_y ) )
    dist812_x = coefInconnu * dist48_x
    dist812_y = coefInconnu * dist48_y
    corners[12] = ( int( corners[8][0] + dist812_x ), int( corners[8][1] + dist812_y ) )

    return corners


def _draw(img, imgpts):
    imgpts = np.float32(imgpts).reshape(-1,2)
    lineWidth = 2
    borderColor = (154,18,179)

    corners = _generatePlateCorners(imgpts)

    # Get the intersection point between 01 and 23
    intersection0123 = _getIntersectionPoint( [imgpts[0],imgpts[1]], [imgpts[2],imgpts[3]] )
    # Get the intersection point between 12 and 30
    intersection1230 = _getIntersectionPoint( [imgpts[1],imgpts[2]], [imgpts[3],imgpts[0]] )

    cv2.line(img, tuple(imgpts[0]), ( intersection1230[0], intersection1230[1] ) , borderColor, lineWidth)
    cv2.line(img, tuple(imgpts[1]), ( intersection1230[0], intersection1230[1] ) , borderColor, lineWidth)
    cv2.line(img, corners[2], ( intersection1230[0], intersection1230[1] ) , borderColor, lineWidth)
    cv2.line(img, corners[3], ( intersection1230[0], intersection1230[1] ) , borderColor, lineWidth)

    cv2.line(img, tuple(imgpts[0]), ( intersection0123[0], intersection0123[1] ) , borderColor, lineWidth)
    cv2.line(img, tuple(imgpts[3]), ( intersection0123[0], intersection0123[1] ) , borderColor, lineWidth)
    cv2.line(img, corners[8], ( intersection0123[0], intersection0123[1] ) , borderColor, lineWidth)
    cv2.line(img, corners[12], ( intersection0123[0], intersection0123[1] ) , borderColor, lineWidth)


def _getIntersectionPoint( seg1, seg2 ):
    # y = ax+b
    # a = (y0-y1)/(x0-x1)
    dirCoef_segment_1 = ( seg1[0][1] - seg1[1][1] ) / ( seg1[0][0] - seg1[1][0] )
    dirCoef_segment_2 = ( seg2[0][1] - seg2[1][1] ) / ( seg2[0][0] - seg2[1][0] )
    # b = y0 - a*x0
    origin_segment_1 = seg1[0][1] - ( dirCoef_segment_1 * seg1[0][0] )
    origin_segment_2 = seg2[0][1] - ( dirCoef_segment_2 * seg2[0][0] )

    # x of intersection = (b2-b1)/(a1-b2)
    intersection_x = ( origin_segment_2 - origin_segment_1 ) / ( dirCoef_segment_1 - dirCoef_segment_2 )
    # y corresponding
    intersection_y = ( dirCoef_segment_1 * intersection_x ) + origin_segment_1
    return [ intersection_x, intersection_y ]


def _play(action, img, imgpts):
    case = int(action[2])

    if( action[1] == 'A' ):
        case += 0
    elif( action[1] == 'B' ):
        case += 4
    elif( action[1] == 'C' ):
        case += 8
    else:
        print "Problem in case detection"

    # Read symbol to play
    if( action[0] == 'C' ):
        color = (242, 38, 19)
    elif( action[0] == 'R' ):
        color = (30, 130, 76)
    else:
        print "Problem in form detection"
        return

    imgpts = np.float32(imgpts).reshape(-1,2)
    width = 3
    cv2.line(img, tuple(imgpts[case]), tuple(imgpts[case+5]), color, width)
    cv2.line(img, tuple(imgpts[case+4]), tuple(imgpts[case+1]), color, width)


class image_feature:

    def __init__(self):

        self.initialized = 0
        self.last_treatment = 0

        '''Initialize ros publisher, ros subscriber'''
        # topic where we publish
        self.image_pub = rospy.Publisher("/output/image_raw/compressed",
            CompressedImage)
        # self.bridge = CvBridge()

        # subscribed Topic
        self.subscriber = rospy.Subscriber("/usb_cam/image_raw/compressed",
            CompressedImage, self.callback,  queue_size = 1)
        if VERBOSE :
            print "subscribed to /usb_cam/image_raw/compressed"


    def callback(self, ros_data):
        '''Callback function of subscribed topic. 
        Here images get converted and features detected'''
        if VERBOSE :
            print 'received image of type: "%s"' % ros_data.format

        #### direct conversion to CV2 ####
        np_arr = np.fromstring(ros_data.data, np.uint8)
        image_np = cv2.imdecode(np_arr, cv2.CV_LOAD_IMAGE_COLOR)

        # Treat only image after img_treatment_freq (in ns) passed
        now = rospy.Time.now()
        now_ns = 1000000000 * now.secs + now.nsecs # time in ns
        img_treatment_freq = 1000000000 # 1 s
        if( now_ns - self.last_treatment >= img_treatment_freq ):
            # Arrays to store object points and image points from all the images.
            objpoints = [] # 3d point in real world space
            imgpoints = [] # 2d points in image plane.

            # convert np image to grayscale
            gray = cv2.cvtColor(image_np,cv2.COLOR_BGR2GRAY)

            # Detect pattern (chessboard)
            ret, corners = cv2.findChessboardCorners(gray, (chessHeight,chessWidth), None) 

            # If found, add object points, image points (after refining them)
            if ret == True:
                objpoints.append(objp)

                cv2.cornerSubPix(gray,corners,(11,11),(-1,-1),criteria)
                imgpoints.append(corners)

                if (self.initialized == 0):
                    self.initialized = 1;
                    ret, self.camera_mtx, self.camera_dist, self.camera_rvecs, self.camera_tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1],None,None)

                # Find the rotation and translation vectors.
                self.camera_rvecs, self.camera_tvecs, inliers = cv2.solvePnPRansac(objp, corners, self.camera_mtx, self.camera_dist)

                # project 3D points to image plane
                imgpts, jac = cv2.projectPoints(axis, self.camera_rvecs, self.camera_tvecs, self.camera_mtx, self.camera_dist)

                self.previous_corners = corners
                self.previous_imgpts = imgpts

            # Save last treatment
            self.last_treatment = now_ns

        if (self.initialized == 1):
            #_draw(image_np,self.previous_imgpts)
            _draw(image_np,self.previous_imgpts)
           # _play("CB2", image_np, self.previous_imgpts)
           # _play("CB0", image_np, self.previous_imgpts)
           # _play("CA0", image_np, self.previous_imgpts)
           # _play("RA1", image_np, self.previous_imgpts)
           # _play("RC2", image_np, self.previous_imgpts)
           # _play("RC0", image_np, self.previous_imgpts)


        # Draw and display the corners
        cv2.imshow('cv_img', image_np)
        cv2.waitKey(5)

        #### Create CompressedIamge ####
        msg = CompressedImage()
        msg.header.stamp = rospy.Time.now()
        msg.format = "jpeg"
        msg.data = np.array(cv2.imencode('.jpg', image_np)[1]).tostring()
        # Publish new image
        self.image_pub.publish(msg)


def main(args):
    '''Initializes and cleanup ros node'''
    ic = image_feature()
    rospy.init_node('image_feature', anonymous=True)
    try:
        rospy.spin()
    except KeyboardInterrupt:
        print "Shutting down ROS Image feature detector module"
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main(sys.argv)
