from cv2 import cv2
import numpy as np
import time
from tkinter import messagebox
import pandas
import fnmatch

def trace_ROI(App):
    global parameters, i, drawingROI, drawingCL, selectedLine, ROImask, ROI, cut_lines

    def updateSTrackbar(value):
        global i
        i = value
        return

    def initialize_mask(parameters):
        # global parameters
        # Compute the ROI mask once to keep it in memory
        roi_norm_str = eval(str(parameters['ROI']))
        if roi_norm_str:
            roi_norm = np.asarray(roi_norm_str)
            roi = (roi_norm * [parameters['width'], parameters['height']]).astype(int)  # scale ROI with image size, round to nearest pixel
            roi_mask = np.zeros((parameters['height'], parameters['width']), dtype=np.uint8)
            ROI_mask = cv2.drawContours(image=roi_mask, contours=[roi], contourIdx=0, color=(255, 255, 255),
                                            thickness=-1)
        else:
            roi = np.array([[0, 0]], dtype=np.int32)  # ROI contour
            ROI_mask = np.ones((parameters['height'], parameters['width']), dtype=np.uint8)

        return roi, ROI_mask

    def initialize_cut_line(parameters):
        # Builds the cut_lines array from the parameters
        # Cut line specified in the parameters file in normalized coordinates
        # (x1,y1), (x2,y2): read in, scale into image coordinates
        
        # Get all parameter fields that begin with 'cutLine
        cutline_keys = fnmatch.filter(parameters.keys(), 'Cut_Line*')
        cut_lines = []
        for key in cutline_keys:
            cutLine_norm_str = eval(str(parameters[key]))
            if cutLine_norm_str:
                cutLine_norm = np.asarray(cutLine_norm_str)
                cutLine = (cutLine_norm * [parameters['width'], parameters['height']]).astype(int)  # scale cut line with image size, round to nearest pixel
            else:
                cutLine = np.array([[0, 0]], dtype=np.int32)  # default cut line
            cut_lines.append(cutLine)
        return cut_lines

    def selectLine(event, x, y, flags, params):
        global drawingROI, drawingCL, selectedLine, ROI, ROImask, cut_lines, parameters
        if mode == 'ROI':
            if drawingROI:
                ROI[-1] = [x, y]
            if event == cv2.EVENT_LBUTTONDOWN:  # Left click
                if not drawingROI:
                    ROI = np.array([[0, 0]], dtype=np.int32)
                    ROI[-1] = [x, y]
                    drawingROI = True
                ROI = np.append(ROI, [[x, y]], axis=0)

            if event == cv2.EVENT_RBUTTONDOWN:  # Right click
                # print('ROI (absolu) : \n{}\n'.format([[couple[0],couple[1]] for couple in ROI]))
                ROI_rel = np.zeros_like(ROI, dtype=float)
                ROI_rel[:, 0] = np.around(ROI[:, 0] / parameters['width'], decimals=2)
                ROI_rel[:, 1] = np.around(ROI[:, 1] / parameters['height'], decimals=2)
                strInfo = 'ROI : {}'.format([[couple[0],couple[1]] for couple in ROI_rel])
                print(strInfo + '\n')
                try:
                    App.Info.set(strInfo)
                except:
                    pass
                drawingROI = False
                ROImask = np.zeros((parameters['height'], parameters['width']), dtype=np.uint8)
                cv2.drawContours(ROImask, [ROI], 0, (255, 255, 255), -1)
                parameters['ROI'] = str([[couple[0],couple[1]] for couple in ROI_rel])# + '\n'

        if mode == 'CL':
            if drawingCL:
                cut_lines[selectedLine-1][-1] = [x, y]
            if event == cv2.EVENT_LBUTTONDOWN:  # Left click
                if not drawingCL:
                    cut_lines[selectedLine-1] = np.array([[0, 0]], dtype=np.int32)
                    cut_lines[selectedLine-1][-1] = [x, y]
                    drawingCL = True    
                cut_lines[selectedLine-1] = np.append(cut_lines[selectedLine-1], [[x, y]], axis=0)

            if event == cv2.EVENT_RBUTTONDOWN:
                # print('Ligne de coupe (absolu) : \n{}\n'.format([[couple[0],couple[1]] for couple in cut_line]))
                cut_lineRel = np.zeros_like(cut_lines[selectedLine-1], dtype=float)
                cut_lineRel[:, 0] = np.around(cut_lines[selectedLine-1][:, 0] / parameters['width'], decimals=2)
                cut_lineRel[:, 1] = np.around(cut_lines[selectedLine-1][:, 1] / parameters['height'], decimals=2)
                strInfo = 'Ligne de coupe #{} : {}'.format(selectedLine,[[couple[0],couple[1]] for couple in cut_lineRel])
                print(strInfo + '\n')
                try:
                    App.Info.set(strInfo)
                except:
                    pass
                drawingCL = False
                parameters['Cut_Line' + str(selectedLine)] = str([[couple[0],couple[1]] for couple in cut_lineRel])# + '\n'

    drawingROI = False # Tracé du ROI en cours
    drawingCL = False # Tracé de la Cut Line en cours
    selectedLine = 0 # CutLine selected
    mode = 'ROI' # 'ROI' ou 'CL'
    showHelp = True

    parameters = App.parameters.copy()
    try:
        videoPath = App.VideoPath.get()
        excelPath = App.ExcelPath.get()
    except:
        videoPath = App.VideoPath
        excelPath = App.ExcelPath

    cap = cv2.VideoCapture(videoPath)

    time.sleep(0.5)
    if not cap.isOpened():
        strInfo = 'Impossible d\'ouvrir : {}'.format(videoPath)
        print(strInfo)
        try:
            App.Info.set(strInfo)
        except:
            pass
        return

    tots = cap.get(cv2.CAP_PROP_FRAME_COUNT)  # Set to a negative number for streaming
    parameters['width'] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    parameters['height'] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cv2.namedWindow('Video Player', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Video Player', parameters['width'], parameters['height'])
    cv2.moveWindow('Video Player', 50, 50)
    if tots > 0:
        cv2.createTrackbar('S', 'Video Player', 0, int(tots) - 1, updateSTrackbar)

    cv2.setMouseCallback('Video Player', selectLine)

    status = 'play'
    isRunning = True
    i = 1

    cut_lines = initialize_cut_line(parameters)
    ROI, ROImask = initialize_mask(parameters)

    # Reading loop
    while True:
        try:
            status = {
                ord(' '):   'play/pause',
                ord('r'):   'reset',
                9:          'switch mode', # Tab
                38:         'sel1', # &
                49:         'sel1', # 1
                233:        'sel2', # é
                50:         'sel2', # 2
                34:         'sel3', # "
                51:         'sel3', # 3
                39:         'sel4', # '
                52:         'sel4', # 4
                ord('h'):   'switch help',
                -1:         status,
                27:         'exit'}[cv2.waitKey(1)]

            if (cv2.getWindowProperty('Video Player',1) == -1) & (i>1):  # The user closed the window
                status = 'exit'

            if status == 'play': # mettre en bas ?
                i += 1
                i%=tots

            if tots > 0:  # The two next lines slow down the code a lot !
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
                cv2.setTrackbarPos('S', 'Video Player', int(i))

            _, im = cap.read()

            opacity = 0.7
            overlay = im.copy()  # for transparency

            if np.size(ROI) > 2:
                cv2.drawContours(overlay, [ROI], 0, (255, 255, 255), 2)
                if not drawingROI:
                    overlay = cv2.bitwise_and(overlay, overlay, mask=ROImask)

            for ii, cut_line in enumerate(cut_lines):
                if np.size(cut_line) > 2:
                    if (selectedLine-1)==ii:
                        cv2.polylines(overlay, [cut_line], 0, (0, 0, 255), 5)
                    else:
                        cv2.polylines(overlay, [cut_line], 0, (255, 255, 255), 3)

            cv2.addWeighted(overlay, opacity, im, 1 - opacity, 0, im)

            if mode == 'ROI':
                txt = 'Selection du ROI'
            elif mode == 'CL':
                txt = 'Selection de la ligne de coupe #{}'.format(selectedLine)
            textdim, _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)
            cv2.rectangle(im, (5, 22), (5 + textdim[0], 20 - textdim[1]), (255, 255, 255), -1)
            cv2.putText(im, txt, (5, 20), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)

            dy = 20
            if showHelp:
                if mode == 'ROI':
                    txt = 'r : remettre a zero le ROI'
                    cv2.putText(im, txt, (5, parameters['height']-5*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                    if not drawingROI:
                        txt = 'clic gauche : selectionner le premier point du ROI'
                        cv2.putText(im, txt, (5, parameters['height']-4*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                    elif drawingROI:
                        txt = 'clic gauche : selectionner le point suivant du ROI'
                        cv2.putText(im, txt, (5, parameters['height']-4*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                        txt = 'clic droit : selectionner le dernier point du ROI'
                        cv2.putText(im, txt, (5, parameters['height']-3*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                    txt = 'Tab : passer a la selection de la ligne de coupe' 
                    cv2.putText(im, txt, (5, parameters['height']-2*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                elif mode == 'CL':
                    txt = '1-4 : selectionner la ligne de coupe #1-4'
                    cv2.putText(im, txt, (5, parameters['height']-6*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                    txt = 'r : remettre a zero la ligne de coupe #{}'.format(selectedLine)
                    cv2.putText(im, txt, (5, parameters['height']-5*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                    if not drawingCL:
                        txt = 'clic gauche : selectionner le premier point de la ligne de coupe'
                        cv2.putText(im, txt, (5, parameters['height']-4*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                    elif drawingCL:
                        txt = 'clic gauche : selectionner le point suivant de la ligne de coupe'
                        cv2.putText(im, txt, (5, parameters['height']-4*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                        txt = 'clic droit : selectionner le dernier point de la ligne de coupe'
                        cv2.putText(im, txt, (5, parameters['height']-3*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                    txt = 'Tab : passer a la selection du ROI'
                    cv2.putText(im, txt, (5, parameters['height']-2*dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                txt = 'Esc : quitter'
                cv2.putText(im, txt, (5, parameters['height']-dy), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                txt = 'h : cacher l\'aide'
                cv2.putText(im, txt, (5, parameters['height']-1), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
            else:
                txt = 'h : montrer l\'aide'
                cv2.putText(im, txt, (5, parameters['height']-1), cv2.FONT_HERSHEY_DUPLEX, 0.5, 1, 1)
                
            cv2.imshow('Video Player', im)
            if status == 'play':
                continue

            elif status == 'stay':
                i = int(cv2.getTrackbarPos('S', 'Video Player'))

            elif status == 'play/pause':
                status = 'stay' if isRunning else 'play'
                isRunning = not isRunning

            elif status == 'reset':
                if mode == 'ROI':
                    parameters['ROI'] = None
                    ROI, ROImask = initialize_mask(parameters)
                elif mode == 'CL':
                    parameters['Cut_Line'+str(selectedLine)] = None
                    cut_lines = initialize_cut_line(parameters)
                status = 'play' if isRunning else 'stay'

            elif status == 'switch mode':
                if mode == 'ROI':
                    mode = 'CL'
                    selectedLine = 1
                else:
                    mode = 'ROI'
                    selectedLine = 0
                status = 'play' if isRunning else 'stay'

            elif status == 'sel1':
                if not drawingCL:
                    selectedLine = 1
                    mode = 'CL'
                    status = 'play' if isRunning else 'stay'  

            elif status == 'sel2':
                if not drawingCL:
                    selectedLine = 2
                    mode = 'CL'
                    status = 'play' if isRunning else 'stay'

            elif status == 'sel3':
                if not drawingCL:
                    selectedLine = 3
                    mode = 'CL'
                    status = 'play' if isRunning else 'stay'  

            elif status == 'sel4':
                if not drawingCL:
                    selectedLine = 4
                    mode = 'CL'
                    status = 'play' if isRunning else 'stay'  

            elif status == 'switch help':
                showHelp = not showHelp
                status = 'play' if isRunning else 'stay'  

            elif status == 'exit':
                answer = messagebox.askquestion(message='Voulez vous enregistrer les modifications dans le fichier de paramètres ?', type='yesnocancel')
                if answer == 'cancel':
                    status = 'play' if isRunning else 'stay'
                if answer == 'yes':
                    App.parameters = parameters # Ecraser les anciens paramètres avec les nouveaux
                    df = pandas.read_excel(excelPath, header=None)
                    try:
                        df.loc[App.comboBoxID.current()+1, 9] = parameters['ROI']
                        for ii in range(1,5):
                            df.loc[App.comboBoxID.current()+1, 9+ii]  = parameters['Cut_Line' + str(ii)]
                    except:
                        df.loc[2, 9] = parameters['ROI']
                        for ii in range(1,5):
                            df.loc[2, 9+ii]  = parameters['Cut_Line' + str(ii)]                       
                    try:
                        with pandas.ExcelWriter(excelPath) as writer:
                            df.to_excel(writer, header=None, index=False, sheet_name='All')
                            writer.save
                    except PermissionError:
                        messagebox.showerror(title='Erreur', message='Impossible d\'enregistrer les modifications, vérifier que le fichier n\'est pas utilisé par une autre application')
                        status = 'play' if isRunning else 'stay'
                        continue
                    break
                if answer == 'no':
                    break

        except KeyError as e:
            print("Invalid Key \"{:s}: {:d}\" was pressed".format(chr(e.args[0]), e.args[0]))

    cv2.destroyAllWindows()
    cap.release()
    return

    
if __name__ == '__main__':
    from collections import namedtuple
    Application = namedtuple('Application','parameters ROI')
    App = Application
    App.parameters = {}
    App.parameters['ROI'] = None
    App.parameters['Cut_Line1'] = None
    App.parameters['Cut_Line2'] = None
    App.parameters['Cut_Line3'] = None
    App.parameters['Cut_Line4'] = None
    App.VideoPath = 'F:\\Python Projects\\SkImage_ROI_CL\\video_test.avi'
    # App.VideoPath = 'rtsp://root:I1Gryp=i@147.173.197.206/axis-media/media.amp?'
    App.ExcelPath = 'F:\\Python Projects\\SkImage_ROI_CL\\skimage_parameters.xlsx'
    App.Info = ''
    trace_ROI(App)