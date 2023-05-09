import numpy as np

def bbox_boarder_dist_simple(bboxes1, bboxes2):
    '''
    Compute boarder distance simple version
    :param bboxes1: Nx4
    :param bboxes2: Mx4
    :return xd_mat: NxM boarder distance matrix in horizontal direction
    :return yd_mat: NxM boarder distance matrix in vertical direction
    '''
    if not isinstance(bboxes1, np.ndarray):
        bboxes1 = np.asarray(bboxes1)
        bboxes2 = np.asarray(bboxes2)

    x11, y11, x12, y12 = np.split(bboxes1, 4, axis=1)
    x21, y21, x22, y22 = np.split(bboxes2, 4, axis=1)

    # compute boarder distance distance in y dimension
    yd1 = np.subtract(y12, np.transpose(y21))
    yd2 = np.subtract(y11, np.transpose(y22))

    middle_y = ((yd1 > 0).astype('float')*(yd2 < 0).astype('float'))
    bbox2_below = (yd1 <= 0).astype('float')
    bbox1_below = (yd2 >= 0).astype('float')
    yd_mat = middle_y * 0. + \
             bbox2_below * np.abs(yd1) + \
             bbox1_below * np.abs(yd2)

    # compute boarder distance distance in x dimension
    xd1 = np.subtract(x11, np.transpose(x22))
    xd2 = np.subtract(x12, np.transpose(x21))

    middle_x = ((xd1 < 0).astype('float') * (xd2 > 0).astype('float'))
    bbox2_right = (xd2 <= 0).astype('float')
    bbox1_right = (xd1 >= 0).astype('float')
    xd_mat = middle_x * 0. + \
             bbox2_right * np.abs(xd2) + \
             bbox1_right * np.abs(xd1)

    return yd_mat, middle_y, bbox1_below, bbox2_below,\
           xd_mat, middle_x, bbox1_right, bbox2_right


