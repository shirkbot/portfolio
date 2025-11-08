import tkinter as tin
from tkinter import ttk

from [redacted] import [redacted] as [redacted]

util_instance = [redacted]()

class UtilsWindow():

    # Dict of all config names and their checkboxs
    values = {}

    def __init__(self, root):
        # Main Window
        root.title("Pipeline Config Utils")

        # frame for controlling window size
        frm_master = tin.Frame(root)

        # Decorative label so people know what they're looking at
        label = tin.Label(frm_master, text="Pipeline Config Utils", font=('Calibiri', 18))
        label.grid(column=0, row=0)

        # Frame for the list of configs
        config_list = tin.LabelFrame(frm_master, text="Configs")
        config_list.grid(column=0, row=1)

        # de/select all buttons
        frm_select_all = tin.Frame(config_list)
        frm_select_all.pack(fill='x')

        btn_select_all = tin.Button(frm_select_all, text='Select All', command=self.select_all)
        btn_deselect_all = tin.Button(frm_select_all, text='Deselect All', command=self.deselect_all)

        btn_deselect_all.grid(row=0, column=0, sticky='e')
        btn_select_all.grid(row=0, column=1, sticky='e')

        # order the config list alphabetically
        config_names = sorted(util_instance.dev_paths_dict.keys())

        # Frames containing the config name and a checkbox
        for config_name in config_names:
            config_frame = tin.Frame(config_list)

            config_label = tin.Label(config_frame, text=config_name)
            config_label.pack(side='left', padx=5)

            val = tin.IntVar(value=1)
            checkbox = tin.Checkbutton(config_frame, variable=val)
            checkbox.pack(side='right', padx=5)

            config_frame.pack(fill="x")
            self.values.update({config_name: val})

        # Frame for holding all the buttons
        button_frame = tin.Frame(frm_master)
        button_frame.grid(column=1, row=1, padx=10)

        # buttons
        btn_single_config_update = tin.Button(
            button_frame, 
            text="Update Config(s) from Git", 
            pady=10, 
            command=self.single_config_update)

        btn_initial_config_corrections = tin.Button(
            button_frame, 
            text="Correct Template References", 
            pady=10, 
            command=self.initial_config_corrections)

        btn_replace_templates = tin.Button(
            button_frame, 
            text="Remove Git-conflicting Templates", 
            pady=10, 
            command=self.replace_templates)

        btn_run_cache_apps = tin.Button(
            button_frame, 
            text="Run tank cache_apps", 
            pady=10, 
            command=self.run_cache_apps)

        btn_run_push_config = tin.Button(
            button_frame, 
            text="Open cmd Windows for Projects", 
            pady=10, 
            command=self.run_push_config)

        #TODO Work out a proper method for generating Show Tools
        btn_generate_showtools = tin.Button(
            button_frame, 
            text="Generate Showtools", 
            pady=10, 
            command=self.generate_showtools)

        # pack all the buttons
        [
            i.pack(fill='x', pady=5) for i in [
                btn_single_config_update,
                btn_initial_config_corrections,
                btn_replace_templates,
                btn_run_cache_apps,
                btn_run_push_config,
                btn_generate_showtools,
                ]
        ]

        # pack the frame and display the window
        frm_master.pack(padx=10,pady=10)

    # button methods
    # All buttons check for a list of configs, and then require confirmation
    def single_config_update(self):
        print('single_config_update was pressed')
        configs = self.get_checks()
        user_confirm = self.molly_guard()
        if not user_confirm:
            return
        util_instance.bulk_processing('single_config_update', configs)

    def initial_config_corrections(self):
        print('initial_config_corrections was pressed')
        configs = self.get_checks()
        user_confirm = self.molly_guard()
        if not user_confirm:
            return
        util_instance.bulk_processing('initial_config_corrections', configs)

    def replace_templates(self):
        print('replace_templates was pressed')
        template_list = self.select_templates()
        configs = self.get_checks()
        user_confirm = self.molly_guard()
        if not user_confirm:
            return
        util_instance.bulk_processing('replace_templates', configs, template_list)

    def run_cache_apps(self):
        print('run_cache_apps was pressed')
        configs = self.get_checks()
        user_confirm = self.molly_guard()
        if not user_confirm:
            return
        util_instance.bulk_processing('run_cache_apps', configs)

    def run_push_config(self):
        print('run_push_config was pressed')
        configs = self.get_checks()
        user_confirm = self.molly_guard()
        if not user_confirm:
            return
        util_instance.bulk_processing('run_push_config', configs)
        
    def generate_showtools(self):
        print('generate_showtools was pressed')
        configs = self.get_checks()
        if len(configs) > 1:
            print("Select a single config to continue")
            return
            
        user_confirm = self.molly_guard()
        if not user_confirm:
            return

        config = configs[0]
        util_instance.generate_showtools(config)


    # utility methods
    def get_checks(self):
        """
        Generate a list of all configs with checkboxes marked
        """
        print('Generating list of configs to process...')
        processing_list = [config for config, check in self.values.items() if check.get() != 0]
        print(f'returning configs {processing_list}')
        return processing_list

    def select_all(self):
        """
        Mark all checkboxes
        """
        [check.set(1) for config,check in self.values.items()]

    def deselect_all(self):
        """
        Clear all checkboxes
        """
        [check.set(0) for config,check in self.values.items()]

    def select_templates(self):
        """
        Generate a popup to confirm which templates the user wishes to remove
        """
        template_list = TemplateWindow().template_list
        return template_list

    def molly_guard(self):
        """
        Generate a popup to get user confirmation that their config list is final

        NOTE: Main window will be inactive until confirmed or closed
        """
        user_confirm = MollyGuard().confirm
        if not user_confirm:
            print("User has not confirmed config selection. Aborting...")

        return user_confirm

class TemplateWindow():
    
    template_list = []
    # TODO: make a dynamic list of templates
    available_templates = [
        "roots"
        # other templates removed for NDA reasons
    ]

    def __init__(self):
        # Popout Window
        template_window = tin.Toplevel()
        template_window.title("Select Templates")

        # master frame for Template window
        template_master_frm = tin.Frame(template_window)

        # Label to identify popout window
        template_lbls = tin.Label(template_master_frm, text="Select Templates to Replace", font=('Calibiri', 18), padx=10)
        template_lbls.pack(fill='x')

        # Frame to contain list of templates and checkmarks
        template_lblfrm = tin.LabelFrame(template_master_frm, text='Templates')
        template_lblfrm.pack()

        # generate frames with template names and checkmarks
        template_values = {}
        for template in self.available_templates:
            template_frm = tin.Frame(template_lblfrm)

            template_lbl = tin.Label(template_frm, text=template)
            template_lbl.pack(side='left', padx=5)

            val = tin.IntVar()
            template_cbx = tin.Checkbutton(template_frm, variable=val)
            template_cbx.pack(side='right', padx=5)

            template_frm.pack(fill="x")
            template_values.update({template: val})

        # confirmation button
        template_confirm_btn = tin.Button(
            template_master_frm, 
            text="Confirm", 
            pady=10, 
            command=template_window.destroy)
        template_confirm_btn.pack(side='right', padx=50, pady=10)

        # Set window dimensions and render
        template_master_frm.pack(padx=10,pady=10)

        template_window.wait_window()

        # collect list of templates to remove
        self.template_list = [template for template,check in template_values.items() if check.get() != 0]
        print(f"returning templates: {self.template_list}")

class MollyGuard():
    
    confirm = False

    def __init__(self):
        # Popout Window
        guard_window = self.guard_window = tin.Toplevel()
        guard_window.title("Confirm Config Selection")

        # label to identify the window
        guard_lbl = tin.Label(guard_window, text="Confirm Config Selection", font=('Calibiri', 18), padx=10)
        guard_lbl.pack(fill='x')

        # confirmation button
        user_confirm_btn = tin.Button(
            guard_window, 
            text="Confirm", 
            padx=30, 
            pady=30, 
            font=('Calibiri', 24),
            bg="Green",
            command=self.user_confirm)
        user_confirm_btn.pack(padx=50, pady=10)

        guard_window.update()
        # window height,width
        width = guard_lbl.winfo_width()
        height = (guard_lbl.winfo_height() + user_confirm_btn.winfo_height())+50

        # window x,y
        posx = int((guard_window.winfo_screenwidth()/2) - (width/2))
        posy = int((guard_window.winfo_screenheight()/2) - (height/2))

        # final geometry
        guard_window.geometry(f"{width}x{height}+{posx}+{posy}")

        # disable main window while dialog is active
        guard_window.grab_set()
        guard_window.wait_window()

    def user_confirm(self):
        """
        Set confirm value to TRUE for evaluation by main window and destroy dialog
        """
        self.confirm = True
        self.guard_window.destroy()

root = tin.Tk()
window = UtilsWindow(root)
root.mainloop()
