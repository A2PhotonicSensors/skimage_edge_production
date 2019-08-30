from tkinter import *
from tkinter.ttk import *
from tkinter.filedialog import askopenfilename
from tkinter import messagebox
import parameter_parser
import trace_ROI

class Application(Frame):
    def __init__(self, master=None, *args, **kwargs):
        super().__init__(master)
        self.master = master
        self.master.title('SkImage : Sélection de ROI/Ligne de coupe')
        self.master.resizable(False,False)
        # self.master.wm_attributes('-topmost',1)
        self.pack(fill='both', ipady=20, padx=5, pady=5)
        self.create_widgets()

    def create_widgets(self):
        self.ExcelPath = StringVar()
        self.frameExcelSpreadSheet = LabelFrame(self,text='Fichier de paramètres', padding=3)
        self.frameExcelSpreadSheet.pack(fill='x', expand=0, side='top', ipadx=3, ipady=3)
        self.editExcel = Label(self.frameExcelSpreadSheet, width=100, textvariable=self.ExcelPath)
        self.editExcel.pack(side='left')
        self.browseExcel = Button(self.frameExcelSpreadSheet, text='Parcourir', command=self.browse_excel)
        self.browseExcel.pack(side='right')

        self.frameID = LabelFrame(self,text='Identifiant de la caméra', padding=3)
        self.frameID.pack(fill='x', expand=1, side='top', ipadx=3, ipady=3)
        self.comboBoxID = Combobox(self.frameID, values=['Ligne1','Ligne2','Ligne3'], state='disabled')
        self.comboBoxID.pack(side='left')

        self.VideoPath = StringVar()
        self.frameVideo = LabelFrame(self,text='Fichier / flux vidéo', padding=3)
        self.frameVideo.pack(fill='x', expand=1, side='top', ipadx=3, ipady=3)
        self.editVideo = Entry(self.frameVideo, width=100, textvariable=self.VideoPath)
        self.editVideo.pack(side='left')
        self.browseVideo = Button(self.frameVideo, text='Parcourir', command=self.browse_video)
        self.browseVideo.pack(side='right')

        self.Info = StringVar()
        self.InfoLabel = Label(self, textvariable=self.Info)
        self.InfoLabel.pack(fill='x', expand=1, side='top')

        self.buttonOK = Button(self, text='OK', command=self.run_video)
        self.buttonOK.pack(side='right')
        self.buttonQuit = Button(self, text='Quitter', command=self.master.destroy)
        self.buttonQuit.pack(side='right')

        self.Info.set('Charger le fichier de paramètres.')

    def browse_excel(self):
        ExcelPath = askopenfilename(title='Sélectionner le fichier de paramètres', filetypes = [('Fichiers Excel','*.xls;*.xlsx')])
        if not ExcelPath: # Annulé
            return
        try:
            parameters_all = parameter_parser.get_parameters(ExcelPath,ExcelPath, get_all_params=True)
        except:
            messagebox.showerror('Error','Impossible de charger le fichier de paramètres')
            return

        self.parameters_all = parameters_all
        self.ExcelPath.set(ExcelPath)
        self.Info.set('Fichier de paramètres chargé avec succès.')
        self.comboBoxID['state'] = 'readonly'
        self.comboBoxID['values'] = [params['Sensor_Label'] + ' (' + str(params['Sensor_ID']) + ')' for params in self.parameters_all]

    def browse_video(self):
        self.VideoPath.set(askopenfilename(title='Sélectionner le fichier / flux video', filetypes = [('Tous les fichiers','*')]))

    def run_video(self):
        if self.comboBoxID['state'] == 'disabled':
            messagebox.showerror('Error','Charger un fichier de paramètres !!')
            return
        if self.comboBoxID.current() == -1:
            messagebox.showerror('Error','Sélectionner une caméra !!')
            return
        if not self.VideoPath.get():
            messagebox.showerror('Error','Sélectionner un fichier / flux vidéo !!')
            return
        self.parameters = self.parameters_all[self.comboBoxID.current()]
        self.Info.set('')
        trace_ROI.trace_ROI(self)
        self.parameters_all[self.comboBoxID.current()] = self.parameters # Récupérer les nouvelles valeurs




root = Tk()
app = Application(master=root)
app.mainloop()