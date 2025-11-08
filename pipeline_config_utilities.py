import getpass
import os
import re
import shutil
import subprocess

from datetime import datetime

class PipelineConfigUtils():

    # core variables
    dev_paths_dict = {}
    sg_returns = None
    
    def __init__(self):
        # Instance SG Engine
        try:
            # Instance Shotgun Engine from [redacted]
            from [redacted] import [redacted]
            eng = sg_connection.sg_connect()
            print("SG Engine from sg_tools")
        except:
            # Instance Shotgun Engine from local API files
            print("Couldn't find sg_connection module, looking for local sgtk")
            import shotgun_api3
            eng = shotgun_api3.shotgun.Shotgun(
                # Args removed for NDA coverage
                )
            print("SG Engine from local API")

        # Query SG for config information
        # Set Shotgun search filters/fields
        filters = [
            # Args removed for NDA coverage
            ]
        fields = # Args removed for NDA coverage

        # Run Shotgun search
        # returns all projects marked "Active"
        self.sg_returns = eng.find("PipelineConfiguration", filters, fields)

        # create mapped drive path with string replacement variable
        # this is used in place of os.path.join because path.join creates literal \\ character
        mapped_drives = {
            # Args removed for NDA coverage
        }

        for config in self.sg_returns:
            network_path = config.get('windows_path')
            root_name = # Args removed for NDA coverage

            # remove anything that doesn't have a Windows path
            if not network_path:
                print("%s missing windows path" % root_name)
                continue


            # remove Pipeline configs
            if root_name in [
                # Args removed for NDA coverage
                ]:
                continue

            storage_name = config['project.Project']['local_storage']['name']

            path_split = [i for i in network_path.split('\\') if i]
            drive_map = [mapped_drives.get(path_split[0])]
            drive_map.extend(path_split[2:])
            mapped_path = "\\".join(drive_map)
            
            self.dev_paths_dict.update({
                drive_map[-1]: {
                    # Args removed for NDA coverage
                }
            })
            print("%s:  %s" % (
                storage_name,
                path_split
            ))

    def set_path_dict(self, current_dir):
        """
        create a set of paths that includes all .yml files in need of replacements

        :current_dir: root path
        """
        # Sets necessary paths to loop through for editing
        git_dir = os.path.join(current_dir, 'config')
        core_dir = os.path.join(git_dir, 'core')
        includes_dir = os.path.join(core_dir, 'includes')
        schema_dir = os.path.join(core_dir, 'schema')

        dir_dictionary = {
            "core": {
                "path": core_dir,
                "files": ['roots', 'templates', 'install_location']
            },
            "includes": {
                "path": includes_dir,
                "files": [os.path.splitext(template_file)[0] for template_file in os.listdir(includes_dir) if os.path.splitext(template_file)[-1] != ".old"]
            },
            "schema": {
                "path": schema_dir,
                "files": ['project']
            },
        }

        return dir_dictionary

    def generate_showtools(self, storage_root_name):
        """
        generate a show folder in [redacted]

        :param: storage_root_name - name of the storage root in SG  
        """
        # isolate the root
        root = next((i for i in self.sg_returns if str(i.get('windows_path')).endswith(storage_root_name)), None)
        
        # capture name to assign directory
        root_name = root.get('project.Project', {}).get('name')

        showtools_redacted2 = "[redacted]"
        showtools_redacted = "[redacted]"

        # TODO Migrate ShowTools to Pix
        showtools_root = showtools_redacted2
        if os.path.exists(showtools_redacted):
            showtools_root = showtools_redacted

        # Configure paths to copy and destination
        template_name = "_TEMPLATE"
        showtools_template = os.path.normpath(os.path.join(showtools_root, template_name))
        showtools_dir = re.sub(template_name, root_name, showtools_template)

        if not os.path.exists(showtools_dir):
            print(f"Generating show_tools directory for: {showtools_dir}")
            shutil.copytree(showtools_template, showtools_dir)

    def single_config_update(self, config):
        """
        Creates/clones a config folder with a git directory
        and creates a backup of the previous config folder in case of emergency

        :config: Specific config folder name in Configs directory
        """
        # Set current directory
        dev_path_info = self.dev_paths_dict.get(config)
        current_dir = dev_path_info.get('mapped_path')

        # Get the name of the current user
        user = getpass.getuser()
        time = datetime.now()
        timestamp = time.strftime('%Y%m%d_%H%M%S')

        # config root of dir\\config and backup directory
        config_root = os.path.join(current_dir, 'config')
        backup_dir = os.path.join(current_dir, 'config.bak', 'config.{timestamp}.{user}'.format(timestamp=timestamp, user=user))

        # create a cmd string using %s or fstring because .format displays as an extension of the web address
        cmd_string = f"cd /d {config_root} & git pull [redacted]"

        # Create a backup of the current config folder and pull latest config settings from Github
        try:
            print('Creating config backup')
            shutil.copytree(config_root, backup_dir)

            print(f'Attempting git pull for {config}')
            subprocess.call(cmd_string, shell=True)

        # Create a fresh config directory and pull the latest config settings from Github
        except:
            print('No config, Creating new git directory')
            os.makedirs(config_root)

            print('Creating config backup')
            subprocess.call(f"cd /d {config_root} & git init", shell=True)

            print(f'Attempting git pull for {config}')
            subprocess.call(cmd_string, shell=True)

    def initial_config_corrections(self, config):
        """
        Replaces all references to Pipeline within key yml files
        """

        # Sets current directory path and retrieves the project root name
        dev_path_info = self.dev_paths_dict.get(config)
        current_dir = dev_path_info.get('mapped_path')
        project_root = dev_path_info.get('redacted_storage')

        # Sets necessary paths to loop through for editing
        dir_dictionary = self.set_path_dict(current_dir)
        
        print(f"processing {config}...")
        for location, info in dir_dictionary.items():
            for file_name in info['files']:
                dir_file = os.path.join( info['path'], file_name )
                clone_doc = open( f'{dir_file}_clone.txt', 'a' )

                try:
                    # convert yml file to txt for easier editing
                    # (because I don't want to import more modules)
                    os.rename( f'{dir_file}.yml', f'{dir_file}.txt' )
                    temp_file = open( f'{dir_file}.txt', 'r' )
                    read_of_file = temp_file.read()
                    temp_file.close()

                    # Check for existing .old file and overwrite it, or create a new one
                    try:
                        doc_check = open( f'{dir_file}.yml.old' )
                        doc_check.close()
                        os.remove( f'{dir_file}.yml.old' )
                        os.rename( f'{dir_file}.txt', f'{dir_file}.yml.old' )
                    except:
                        os.rename( f'{dir_file}.txt', f'{dir_file}.yml.old' )

                    count = 0

                    # The actual replacements happen here
                    for read_line in read_of_file.split( '\n' ):
                        if 'windows_path' in read_line or 'linux_path' in read_line:
                            clone_doc.write( read_line.replace( 'project_pipeline', project_root.replace('[redacted]','') ) + '\n' )
                            count +=1
                        elif 'project_pipeline' in read_line:
                            clone_doc.write( read_line.replace( 'project_pipeline', project_root ) + '\n' )
                            count +=1
                        else:
                            clone_doc.write( read_line + '\n' )

                    print( f'{str(count)} instances of "project_pipeline" in {dir_file}.yml' )

                except:
                    print( 'No such file' )

                # Close document and convert it to a .yml so it can be read correctly by Shotgun
                clone_doc.close()
                os.rename( f'{dir_file}_clone.txt', f'{dir_file}.yml' )

    def replace_templates(self, config, template_list = []):
        """
        renames an existing template to template.old across all active projects.
        This is intended to be used when doing bulk config updates to clear a common git pull conflict

        :template_to_replace: name of the template.yml file that needs to be removed. If not specified
        """

        dev_path_info = self.dev_paths_dict.get(config)
        current_dir = dev_path_info.get('mapped_path')
        print("Current Directory is " + current_dir)
        
        # Sets necessary paths to loop through for editing
        dir_dictionary = self.set_path_dict(current_dir)

        # add templates.yml and roots.yml to list of template paths
        available_paths = [os.path.join(dir_dictionary['core']['path'], 'roots')]
        available_paths.extend([os.path.join(dir_dictionary['includes']['path'], i) for i in dir_dictionary['includes']['files']])

        if not template_list:
            select_paths = [f"{path}.yml" for path in available_paths]
        elif "templates" in template_list:
            minus_list = [i for i in template_list if i != 'templates']
            template_path = f"{os.path.join(dir_dictionary['core']['path'], 'templates')}.yml"
            select_paths = [f"{path}.yml" for path in available_paths if path.endswith(tuple(minus_list))]
            select_paths.append(template_path)
        else:
            select_paths = [f"{path}.yml" for path in available_paths if path.endswith(tuple(template_list))]

        for item in select_paths:
            try:
                doc_check = open(item + '.old')
                doc_check.close()
                os.remove(item + '.old')
                os.rename(item, item + '.old')
            except:
                os.rename(item, item + '.old')

        print(f"The following templates have been removed from {config}: {select_paths}")

    def run_cache_apps(self, config):
        """
        Opens a cmd window in the specified project config

        :config: Specific config folder name in Configs directory
        """
        dev_path_info = self.dev_paths_dict.get(config)
        current_dir = dev_path_info.get('mapped_path')

        print(f"Caching apps for: {config}")

        subprocess.run(["tank", "cache_apps"], shell=True, cwd=current_dir)

    def run_push_config(self, config):
        """
        Opens a cmd window in the specified project config

        :config: Specific config folder name in Configs directory
        """
        dev_path_info = self.dev_paths_dict.get(config)
        current_dir = dev_path_info.get('mapped_path')

        subprocess.Popen(["start"], shell=True, cwd=current_dir)


    def bulk_processing(self, process, config_list = [], template_list = []):
        """
        Allows for the processing of multiple configs
        but only ONE process at a time, for cleanliness

        :process: name of the process to be run (config_update, config_correction, replace_templates)
        :config_list: list of configs to be processed.
            If not specified runs on all Pipeline Active projects
        :template_list: name of the template .yml file(s) that needs to be removed.
            If not specified clears all template yml files
        """
        # decide what configs to process
        # if no configs are specified, process all Pipeline Active configs
        if not config_list:
            config_list = self.dev_paths_dict.keys()

        # decide how you want to process them
        if process == "single_config_update":
            for config in config_list:
                self.single_config_update(config)
        elif process == "initial_config_corrections":
            for config in config_list:
                self.initial_config_corrections(config)
        elif process == "replace_templates":
            for config in config_list:
                self.replace_templates(config, template_list)
        elif process == "run_cache_apps":
            for config in config_list:
                self.run_cache_apps(config)
        elif process == "run_push_config":
            for config in config_list:
                self.run_push_config(config)

        print(f"END OF BULK {process}")
