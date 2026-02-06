# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import mimetypes
import os
import sys
import re
from datetime import datetime
import json
import sgtk
from tank_vendor import six

log = sgtk.LogManager.get_logger(__name__)

from custompy.db_tools import legacy_utils
from gen.file_utils import path_finder
import gen.base_utils as base_utils

HookBaseClass = sgtk.get_hook_baseclass()

if "win" in sys.platform:
    system_path_variable = "windows_path"
    system_root_variable = "local_path_windows"
elif sys.platform == "linux":
    system_path_variable = "linux_path"
    system_root_variable = "local_path_linux"


class SsBasicSceneCollector(HookBaseClass):
    """
    A basic collector that handles files and general objects.

    This collector hook is used to collect individual files that are browsed or
    dragged and dropped into the Publish2 UI. It can also be subclassed by other
    collectors responsible for creating items for a file to be published such as
    the current Maya session file.

    This plugin centralizes the logic for collecting a file, including
    determining how to display the file for publishing (based on the file
    extension).

    In addition to creating an item to publish, this hook will set the following
    properties on the item::

        path - The path to the file to publish. This could be a path
            representing a sequence of files (including a frame specifier).

        sequence_paths - If the item represents a collection of files, the
            plugin will populate this property with a list of files matching
            "path".

    """
    logger = sgtk.LogManager.get_logger(__name__)

    _user_info = None
    _software_info = None
    _codec_info = None
    _project_info = None
    
    @property
    def common_file_info(self):
        """
        A dictionary of file type info that allows the basic collector to
        identify common production file types and associate them with a display
        name, item type, and config icon.

        The dictionary returned is of the form::

            {
                <Publish Type>: {
                    "extensions": [<ext>, <ext>, ...],
                    "icon": <icon path>,
                    "item_type": <item type>
                },
                <Publish Type>: {
                    "extensions": [<ext>, <ext>, ...],
                    "icon": <icon path>,
                    "item_type": <item type>
                },
                ...
            }

        See the collector source to see the default values returned.

        Subclasses can override this property, get the default values via
        ``super``, then update the dictionary as necessary by
        adding/removing/modifying values.
        """
        if not hasattr(self, "_common_file_info"):
            # do this once to avoid unnecessary processing
            self._common_file_info = super(SsBasicSceneCollector, self).common_file_info
            self._common_file_info.update({
                # todo is the item type camera or alembic?
                "Alembic Camera": {
                    "extensions": ["abc", "fbx"],
                    "icon": self._get_icon_path("alembic.png"),
                    "item_type": "file.camera"
                },
                "Motion Builder FBX": {
                    "extensions": ["fbx"],
                    "icon": self._get_icon_path("fbx.png"),
                    "item_type": "file.motionbuilder",
                },
                "Rendered Image": {
                    "extensions": ["dpx", "exr", "png", "jpg", "jpeg"],
                    "icon": self._get_icon_path("image_sequence.png"),
                    "item_type": "file.image",
                },
                "Texture Image": {
                    "extensions": ["tx", "tga", "dds", "rat"],
                    "icon": self._get_icon_path("texture.png"),
                    "item_type": "file.texture",
                },
                "DMP": {
                    "extensions": ["tif", "tiff"],
                    "icon": self._get_icon_path("dmp.png"),
                    "item_type": "file.image",
                },
                "3D Equalizer": {
                    "extensions": ["3de"],
                    "icon": self._get_icon_path("lens.png"),
                    "item_type": "file.3de",
                },
                "BGEO": {
                    "extensions": ["bgeo", "bgeosc"],
                    "icon": self._get_icon_path("image_sequence.png"),
                    "item_type": "file.houdini.bgeo",
                },
            })
        return self._common_file_info

    @property
    def user_info(self):
        if self._user_info is None:
            ctx = self.parent.engine.context
            user_filter = [
                ['id', 'is', ctx.user['id']],
            ]
            self._user_info = self.parent.shotgun.find_one(
                'HumanUser',
                user_filter,
                ['name', 'login', 'sg_ip_address']
            )
        return self._user_info

    @property
    def software_info(self):
        """
        Test SG for all associated software
        :returns: The SG info of the given softwares
        """
        if self._software_info is None:
            software_filters = [
                ['id', 'is_not', 0],
                ['dcc_status', 'is_not', 'dis'],
                ['version_names', 'is_not', None]
            ]
            software_fields = [
                'code',
                'products',
                system_path_variable,
                'version_names',
                'pipe_tools'
            ]
            self._software_info = self.parent.shotgun.find(
                'Software',
                software_filters,
                software_fields
            )
        return self._software_info

    @property
    def codec_info(self):
        """
        Test SG for all associated codec

        :returns: The SG info of the given codecs
        """
        if self._codec_info is None:
            self._codec_info = self.parent.shotgun.find(
                'CustomNonProjectEntity08',
                [],
                ['id',
                 'code',
                 'name',
                 'nuke_codec_code',
                 'output_dir']
            )
        return self._codec_info

    @property
    def project_info(self):
        """
        A dictionary of relative Project info that is taken from SG Project page
        Project settings act as a fallback/default
        """
         # TODO use SG manager - make standalone and load the context in
        if self._project_info is None:
            publisher = self.parent
            ctx = publisher.engine.context
            self._project_info = publisher.shotgun.find_one("Project",
                [['id', 'is', ctx.project['id']]],
                ['name',
                    'id',
                    'pr_root',
                    'pr_status',
                    'pr_date_format',
                    'pr_short_name',
                    'pr_frame_rate',
                    'pr_vendor_id',
                    'pr_frame_handles',
                    'pr_data_type',
                    'pr_format_width',
                    'pr_format_height',
                    'pr_delivery_slate_count',
                    'pr_client_version_submission',
                    'pr_incoming_plate_jpg_',
                    'pr_delivery_default_process',
                    'pr_incoming_fileset_padding',
                    'pr_proxy_format_ratio',
                    'pr_format_pixel_aspect_ratio',
                    'pr_lut',
                    'pr_version_zero_lut',
                    'pr_version_zero_slate',
                    'pr_version_zero_internal_burn_in',
                    'pr_burnin_frames_format',
                    'pr_delivery_qt_dual_lut',
                    'pr_delivery_format_width',
                    'pr_delivery_format_height',
                    'pr_delivery_reformat_filter',
                    'pr_delivery_fileset_padding',
                    'pr_delivery_fileset_slate',
                    'pr_zip_fileset_delivery',
                    'pr_pixel_aspect_ratio',
                    'pr_reformat_plates_to_deliverable',
                    'pr_delivery_fileset',
                    'pr_delivery_fileset_compression',
                    'pr_delivery_qt_bitrate',
                    'pr_delivery_qt_slate',
                    'pr_delivery_burn_in',
                    'pr_delivery_qt_codecs',
                    'pr_delivery_qt_formats',
                    'pr_delivery_folder_structure',
                    'pr_color_space',
                    'pr_project_color_management',
                    'pr_project_color_management_config',
                    'pr_timecode',
                    'pr_upload_qt_formats',
                    'pr_review_qt_codecs',
                    'pr_review_burn_in',
                    'pr_review_qt_slate',
                    'pr_review_qt_formats',
                    'pr_slate_frames_format',
                    'pr_frame_leader',
                    'pr_review_lut',
                    'pr_type',
                    'tank_name',
                    'pr_3d_settings']
                )
            self._project_info.update({'artist_name': ctx.user['name']})

            formats = publisher.shotgun.find("CustomNonProjectEntity01",
                [],
                ['code',
                'sg_format_height',
                'sg_format_width',
                ])
            self._project_info.update({'formats': formats})

            storage_id = base_utils.deep_get(self._project_info, "pr_root", "local_storage", "id")

            local_storage = publisher.shotgun.find_one("LocalStorage",
                [["id", "is", storage_id]],
                ["code",
                system_path_variable,
                "linux_path",
                "mac_path"])

            self._project_info['local_storage'] = local_storage.get(system_path_variable)

            if self._project_info['pr_3d_settings']:
                pr_3d_settings = publisher.shotgun.find("CustomNonProjectEntity03",
                    [["id", "is",
                        self._project_info['pr_3d_settings'][0].get('id')]],
                    ['code',
                    'pr_primary_render_layer',
                    'pr_additional_render_layers',
                    'cg_render_engine',
                    ])

                self._project_info.update({'pr_3d_settings': pr_3d_settings})

        return self._project_info

    def process_file(self, settings, parent_item, path):
        """
        Analyzes the given file and creates one or more items
        to represent it.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        :param path: Path to analyze

        :returns: The main item that was created, or None if no item was created
            for the supplied path
        """
        # TODO Check for valid user SG session
        # Without a valid session token all of this is pointless.
        # Declaring variables for later
        entity = {}
        task = {}
        step = {}
        lens = {}
        camera = {}
        primary_render_folder = []
        additional_render_folder = []
        step_bools = None
        file_items = []

        # a path-swap that converts all serv addresses to serv_artist
        path = re.sub(r"^[/\\]{2}serv[a-zA-Z0-9_.]+", r"//serv_artist", path)

        # various utilities
        publisher = self.parent
        ctx = publisher.engine.context
        sg_reader = legacy_utils.SgReader(shotgun=publisher.shotgun)

        # Path string for manipulation
        path = str(sgtk.util.ShotgunPath.normalize(path)).replace('\\', '/')
        self.logger.info('Submission path is: %s' % path)

        # collect basic info about the path and folder
        path_info = self.initial_path_info_returns(path=path)
        curr_fields = path_info.get('all_fields')

        # TODO what if no current fields?
        if curr_fields:
            self.logger.info('curr fields: %s' % curr_fields)
            # run one large shotgun search to collect entity, task, and step info
            # some renders don't have a task_name, we assign these to processing
            task_name = curr_fields.get('task_name') or "processing"
            filters = [
                ["project.Project.id", "is", ctx.project['id']],
                ["content", "is", task_name],
            ]

            entity_type = "entity.%s" % curr_fields['type']
            entity_code = "%s.code" % entity_type
            entity_name = curr_fields['Entity']
            filters.append([entity_code, "is", entity_name])

            # Extra asset filter to ensure the correct asset is being used
            if curr_fields['type'].lower() == "asset":
                filters.append([
                    "%s.en_asset_type" % entity_type, 
                    "is", 
                    curr_fields.get("en_asset_type")
                    ])

            search_fields = self._task_fields(curr_fields)

            entity_info = self.sgtk.shotgun.find_one("Task", filters, search_fields)
            self.logger.info('entity_info: %s' % entity_info)

            # Parse search results into entity, task, step, and camera
            for key, value in entity_info.items():
                key_split = key.split(".")
                set_key = key_split[-1]

                if len(key_split) == 1:
                    task[key] = value

                if key_split[0] == 'step':
                    step[set_key] = value
                elif "en_lens" in key_split:
                    if value:
                        lens[set_key] = value
                elif "en_main_plate_cam" in key_split:
                    camera[set_key] = value
                else:
                    entity[set_key] = value

            # add task id to current fields (holdover from previous version of script)
            if task:
                self.logger.info("Task: %s" % task)
                curr_fields['id'] = task['entity']['id']
            else:
                # FIXME you sure this can go on without failing?
                # todo VALIDATE ALL REQUIREMENTS EARLIER
                # TODO Does this even do anything?
                pass

            # define plugin visibility/enabled
            if step:
                step_bools = self._set_plugins_from_sg(step)

                # evaluate step for 3D-specific settings
                self.logger.info("Step: %s" % step)
                if step['source_dept'] == "3D" and self.project_info['pr_3d_settings']:
                    if self.project_info['pr_3d_settings'][0]['pr_primary_render_layer']:
                        primary_render_folder = self.project_info['pr_3d_settings'][0][
                            'pr_primary_render_layer'].split(",")
                        self.logger.debug("Collected primary layer %s." % primary_render_folder)
                        # TODO Verify if this step is necessary
                        if self.project_info['pr_3d_settings'][0]['pr_additional_render_layers']:
                            for additional in self.project_info['pr_3d_settings'][0][
                                'pr_additional_render_layers'].split(","):
                                additional_render_folder.append(additional)
                            self.logger.debug(
                                "Collected additional %s. Will publish separately." % (additional_render_folder))
                    else:
                        self.logger.debug("Processing 2D submission...")
                else:
                    # FIXME what happens if there's no step?
                    pass

            # manual override for non-version renders
            if not curr_fields.get('task_name'):
                step_bools['step_version_for_review'] = False
                step_bools['step_publish_to_shotgun'] = True
                
            if step_bools:
                self.logger.info("Publish: %s | Version: %s" % (
                    step_bools["step_publish_to_shotgun"],
                    step_bools["step_version_for_review"]))

        # collect the main plate, if there is one
        main_plate = self._get_published_main_plate(
            sg_reader=sg_reader,
            project_id=self.project_info.get('id'),
            entity_id=entity.get('id'),
            step_bools=step_bools
        )

        entity.update({'type': curr_fields['type'],
            'main_plate': main_plate})

        for info in path_info['path_info_returns']:
            if not info.get('fields'):
                continue

            # adjust step_bools for multilayer 3D renders
            layer_bools = {
                'step_publish_to_shotgun': step_bools['step_publish_to_shotgun'],
                'step_version_for_review': step_bools['step_version_for_review'],
            }

            if (step['source_dept'] == "3D" 
            and self.project_info['pr_3d_settings']
            and primary_render_folder
            and len(path_info['path_info_returns']) > 1
            and info.get('base_name') not in primary_render_folder):
                layer_bools = {
                    'step_publish_to_shotgun': True,
                    'step_version_for_review': False,
                }
            elif os.path.splitext(path)[-1] in [".nk", ".ma", ".mb", ".hip", ".ptx"]:
                layer_bools = {
                    'step_publish_to_shotgun': True,
                    'step_version_for_review': False,
                }

            # Construct dictionary of properties with existing values
            properties = {
                # assign properties from path_info values
                'fields': info['fields'],
                'frame_range': info['file_range'],
                'template': info['base_template'],
                'single': info['single'],

                # step and plugin booleans
                'step': step,
                'step_publish_to_shotgun': layer_bools.get('step_publish_to_shotgun'),
                'step_version_for_review': layer_bools.get('step_version_for_review'),

                # other shotgun dictionaries
                'entity_info': entity,
                'task': task,
                'lens': lens,
                'camera': camera,

                # vendor info for outsource
                'vendor': curr_fields.get('vendor'),
                'workfile_dir': info.get('workfile_dir'),
                'publish_path': info.get('publish_path'),

                # templates and other quicktime info
                'extra_templates': self._get_extra_templates(info['fields']),
                'process_plugin_info': info['process_plugin_info'],
                'padded_item_name': info['padded_item_name'],
            }

            if info['single']:
                file_items = [self._collect_file(parent_item, info.get('full_path', path))]
            else:
                file_items = self._collect_folder(parent_item, info.get('directory', path))

            for file_item in file_items:
                # run helper methods and add universal default item properties
                file_item.properties.update(properties)
                self._run_helper_methods(file_item)

        # handle files and folders differently
        if not os.path.isdir(path) and file_items:
            return file_items[0]
        return None

    def _collect_file(self, parent_item, path, frame_sequence=False):
        """
        Process the supplied file path.

        :param parent_item: parent item instance
        :param path: Path to analyze
        :param frame_sequence: Treat the path as a part of a sequence
        :returns: The item that was created
        """
        self.logger.info("Collecting file %s..." % path)
        self.logger.info('frame sequence: %s' % frame_sequence)

        # make sure the path is normalized. no trailing separator, separators
        # are appropriate for the current os, no double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(path)
        publisher = self.parent

        # get info for the extension
        item_info = self._get_item_info(path)
        item_type = item_info["item_type"]
        type_display = item_info["type_display"]

        display_name = publisher.util.get_publish_name(path, sequence=False)

        # create and populate the item
        file_item = parent_item.create_item(item_type, type_display, display_name)
        file_item.set_icon_from_path(item_info["icon_path"])

        # if the supplied path is an image, use the path as the thumbnail.
        if item_type.startswith("file.image") or item_type.startswith("file.texture"):
            file_item.set_thumbnail_from_path(path)
            # disable thumbnail creation since we get it for free
            file_item.thumbnail_enabled = False
        else:
            self.logger.debug("Using icon as thumbnail: %s" % (item_info["icon_path"],))
            file_item.set_thumbnail_from_path(item_info["icon_path"])

        # all we know about the file is its path. set the path in its
        # properties for the plugins to use for processing.
        file_item.properties['path'] = path

        self.logger.debug(">>>>> END COLLECT_FILE >>>>>")
        self.logger.info("Collected file: %s" % (path,))

        return file_item

    def _collect_folder(self, parent_item, folder):
        """
        Process the supplied folder path.

        :param parent_item: parent item instance
        :param folder: Path to analyze
        :returns: The item that was created
        """
        self.logger.debug("Collecting folder contents from %s..." % folder)

        # make sure the path is normalized. no trailing separator, separators
        # are appropriate for the current os, no double separators, etc.
        folder = sgtk.util.ShotgunPath.normalize(folder)

        publisher = self.parent
        img_sequences = publisher.util.get_frame_sequences(
            folder, self._get_image_extensions()
        )
        
        file_items = []
        for (image_seq_path, img_seq_files) in img_sequences:
            # get info for the extension
            item_info = self._get_item_info(image_seq_path)
            item_type = item_info["item_type"]
            type_display = item_info["type_display"]

            # the supplied image path is part of a sequence. alter the
            # type info to account for this.
            type_display = "%s Sequence" % (type_display,)
            item_type = "%s.%s" % (item_type, "sequence")
            icon_name = "image_sequence.png"

            # get the first frame of the sequence. we'll use this for the
            # thumbnail and to generate the display name
            img_seq_files.sort()
            first_frame_file = img_seq_files[0]
            display_name = publisher.util.get_publish_name(
                first_frame_file, sequence=True
            )

            # create and populate the item
            file_item = parent_item.create_item(item_type, type_display, display_name)
            icon_path = self._get_icon_path(icon_name)
            file_item.set_icon_from_path(icon_path)

            # use the first frame of the seq as the thumbnail
            file_item.properties['thumbnail_path'] = file_item.set_thumbnail_from_path(
                first_frame_file) or first_frame_file

            # disable thumbnail creation since we get it for free
            file_item.thumbnail_enabled = False

            # all we know about the file is its path. set the path in its
            # properties for the plugins to use for processing.
            file_item.properties["path"] = image_seq_path
            file_item.properties["sequence_paths"] = img_seq_files

            self.logger.info("Collected file: %s" % (image_seq_path,))

            file_items.append(file_item)

        if not file_items:
            self.logger.warn("No image sequences found in: %s" % (folder,))

        # self.logger.debug(">>>>> Thumbnail: %s" % file_item.properties['thumbnail_path'])
        self.logger.debug(">>>>> END COLLECT_FOLDER >>>>>")

        return file_items

    def _get_item_info(self, path):
        """
        Return a tuple of display name, item type, and icon path for the given
        filename.

        The method will try to identify the file as a common file type. If not,
        it will use the mimetype category. If the file still cannot be
        identified, it will fallback to a generic file type.

        :param path: The file path to identify type info for

        :return: A dictionary of information about the item to create::

            # path = "/path/to/some/file.0001.exr"

            {
                "item_type": "file.image.sequence",
                "type_display": "Rendered Image Sequence",
                "icon_path": "/path/to/some/icons/folder/image_sequence.png",
                "path": "/path/to/some/file.%04d.exr"
            }

        The item type will be of the form `file.<type>` where type is a specific
        common type or a generic classification of the file.
        """

        publisher = self.parent

        # extract the components of the supplied path
        file_info = publisher.util.get_file_path_components(path)
        extension = file_info["extension"]
        filename = file_info["filename"]

        # default values used if no specific type can be determined
        type_display = "File"
        item_type = "file.unknown"

        # keep track if a common type was identified for the extension
        common_type_found = False

        icon_path = None

        # look for the extension in the common file type info dict
        for display in self.common_file_info:
            type_info = self.common_file_info[display]

            if extension in type_info["extensions"]:
                # found the extension in the common types lookup. extract the
                # item type, icon name.
                type_display = display
                item_type = type_info["item_type"]
                icon_path = type_info["icon"]
                common_type_found = True
                break

        if not common_type_found:
            # no common type match. try to use the mimetype category. this will
            # be a value like "image/jpeg" or "video/mp4". we'll extract the
            # portion before the "/" and use that for display.
            (category_type, _) = mimetypes.guess_type(filename)

            if category_type:
                # mimetypes.guess_type can return unicode strings depending on
                # the system's default encoding. If a unicode string is
                # returned, we simply ensure it's utf-8 encoded to avoid issues
                # with toolkit, which expects utf-8
                category_type = six.ensure_str(category_type)

                # the category portion of the mimetype
                category = category_type.split("/")[0]

                type_display = "%s File" % (category.title(),)
                item_type = "file.%s" % (category,)
                icon_path = self._get_icon_path("%s.png" % (category,))

        # fall back to a simple file icon
        if not icon_path:
            icon_path = self._get_icon_path("file.png")

        # everything should be populated. return the dictionary
        return dict(
            item_type=item_type,
            type_display=type_display,
            icon_path=icon_path,
            )

    # set of custom helper methods for cleanliness
    def _set_plugins_from_sg(self, step):
        '''
        Assign correct plugins based on item step

        :param step: The item's task step from Shotgun
        '''

        # Set plugin defaults
        plugins_dict = {
            "step_publish_to_shotgun": True,
            "step_version_for_review": True,
            "step_slap_comp": False
        }

        # Determine which plugins to load
        for key in plugins_dict:
            if step.get(key) is not None:
                plugins_dict[key] = step.get(key)

            if key == "step_version_for_review":
                if not step.get(key):
                    plugins_dict[key] = True
                else:
                    plugins_dict[key] = False

        return plugins_dict

    def _run_helper_methods(self, item):
        """
        Run all the helper methods to complete the collector item

        :param item: the collector item to update/pass to plugins
        """
        path = item.get_property('path')
        publisher = self.parent

        # check for a thumbnail path because os.path.exists() can not do NoneTypes
        prop_path = item.properties.get('thumbnail_path')

        # add thumbnail path to properties and link the task context
        if not prop_path:
            item.properties['thumbnail_path'] = item.get_thumbnail_as_path()
        elif not os.path.exists(prop_path):
            item.properties['thumbnail_path'] = item.get_thumbnail_as_path()

        self._link_task(item)

        # confirm job type by file extension
        file_info = publisher.util.get_file_path_components(path)
        extension = file_info["extension"]
        submit_file_type = next(({i: j} for i, j in self.common_file_info.items() if extension in j['extensions']),
                                None)
        self.logger.info('submit file type %s' % submit_file_type)
        item.properties['submit_file_type'] = submit_file_type

        # determine appropriate software for Deadline operations
        item_software = item.get_property('process_plugin_info')['software']

        set_software = next(
            (i for i in self.software_info if (item_software == i['products'] and i['pipe_tools'] is True)),
            None)
        if not set_software and item_software == "Maya":
            set_software = next((i for i in self.software_info if item_software == i['products']), None)

        item.properties['set_software'] = set_software

        # determine item's source software, we need this to determine what render software to use
        product_list = set([i.get('products').lower() for i in self.software_info])
        delimiter_split = set(path.replace("\\","/").split("/"))
        source_software = delimiter_split.intersection(product_list)
        item.properties['source_software'] = next((dcc for dcc in source_software), None)

        # create copy paths for outsource files
        if item.properties['process_plugin_info'].get('outsource'):
            item.properties['outsource_paths'] = self._get_outsource_paths(item)

        # check for existing version
        item.properties['existing_version'] = self._get_existing_version(item)

        # set version_data for creating a version in Shotgun
        item.properties['version_data'] = self.set_version_data(path, item)

        # set fields to resolve output path
        item.properties['resolve_fields'] = self.set_resolve_fields(item)

        # collect template paths
        item.properties['template_paths'] = self._apply_templates(item)

        # collect review process json as dictionary
        item.properties['review_process_json'] = self._get_process_review_settings(item)

        # collect review process json as dictionary
        item.properties['json_properties'] = self._json_properties(item)
        
        # check for existing playlist and create one if there is none
        item.properties['playlist_info'] = self._get_existing_playlist(item)
        
        return item

    def _link_task(self, item):
        """
        Use Task ID to set context in the publisher GUI

        :param item: the collector item for property assignment
        """
        task = item.get_property('task')
        if not task:
            self.logger.warning(
                'Path does not conform to templates/Could not identify Task. Please set Task/Link manually')
            return
        elif not item.get_property('fields').get('task_name'):
            self.logger.warning('Task are not automatically linked for non-Version renders. Please set Task/Link...')
            return

        item.context = self.sgtk.context_from_entity("Task", task["id"])
        self.logger.info('Context (Task, Link) is ' + str(self.sgtk.context_from_entity("Task", task["id"])))

        return item

    def _get_ampm(self, now):
        '''
        determine appropriate dailies location based on current time

        :param now: a datetime object expressing the current time
        '''
        if int(now.strftime("%H")) < 11:
            return "AM"
        elif int(now.strftime("%H")) < 16:
            return "PM"
        return "LATE"

    def _get_existing_version(self, item):
        """
        Search for existing version in SG and construct version naming
        NOTE: This gets appended to the dictionary in set_version_data later

        :param item: the collector item for property assignment
        """
        publisher = self.parent

        # initial input and basic publisher name
        path = item.get_property('path')
        is_sequence = bool(item.get_property('sequence_paths'))
        full_name = publisher.util.get_publish_name(
            path,
            sequence=is_sequence
        )

        # strip values separated by a . at the end of the name
        name_minus_frames_ext = full_name.split('.', 1)[0]

        # check for version number and either apply it or v000
        version_number = publisher.util.get_version_number(item.get_property("path")) or 0
        underscore_ver = "_v%05d" % version_number

        # build publish and version names by joining with underscores
        publish_name = re.sub("%s$" % underscore_ver, "", name_minus_frames_ext)
        version_name = "%s%s" % (publish_name, underscore_ver)

        # search for version and return result
        existing_version_data = [
            ['project', 'is', {'type': 'Project', 'id': self.project_info['id']}],
            ["code", "is", version_name]
        ]

        version_code = publisher.shotgun.find_one(
            "Version",
            existing_version_data,
            ["code"]
            )

        existing_version = {
            "version": version_code,
            "version_number": version_number,
            "underscore_ver": underscore_ver,
            "version_name": version_name,
            "publish_name": publish_name,
        }

        self.logger.debug("version_name: %s" % version_name)

        return existing_version

    def set_version_data(self, path, item):
        '''
        Generate a version_data dictionary

        :param path: file/folder path
        :param item: the collector item for property assignment
        '''
        # Correct en_path_to_frames for outsource purposes
        en_path_to_frames = path
        outsource_paths = item.get_property("outsource_paths")
        if outsource_paths:
            copy_path = outsource_paths.get("copy_path")
            if copy_path:
                en_path_to_frames = copy_path

        version_data = {
            "code": item.get_property('existing_version').get('version_name'),
            "version_number": item.get_property('existing_version').get('version_number'),
            "frame_range": item.get_property("frame_range"),
            "en_path_to_frames": self._percent_padded_path(en_path_to_frames, item),
            "project": item.context.project,
            "sg_task": item.context.task,
            "entity": item.context.entity,
            "image": item.get_property("thumbnail_path"),
            "publish_name": item.get_property('existing_version').get('publish_name'),
        }

        return version_data

    def set_resolve_fields(self, item):
        '''
        gather fields for template constructions

        :param item: the collector item for property assignment
        '''
        entity_type = item.get_property('fields')['type']
        entity_name = item.get_property('fields')['Entity']
        now = datetime.now()

        # find a field to assign to the name key, if one exists
        name = item.get_property('fields').get('name')
        
        # For 3D renders, the layer name is almost certainly preferable
        software = item.get_property('source_software')
        if software == "maya":
            name = item.get_property('fields').get('maya_layer_name')
            self.logger.info("maya_name: %s" % name)
        elif software == "houdini":
            name = item.get_property('fields').get('node')
            self.logger.info("houdini_name: %s" % name)

        # if there's no detail yet, add output as a detail if it's available
        if not name:
            name = item.get_property('fields').get('output')

        resolve_fields = {
            entity_type: entity_name,
            'task_name': item.context.task['name'],
            'tech_pass': item.get_property('fields').get('tech_pass'),
            'underscore_name': name,
            'version': item.get_property('version_data').get('version_number'),
            'ampm': self._get_ampm(now),
            'YYYY': now.year,
            'MM': now.month,
            'DD': now.day,
            'en_asset_type': item.get_property('fields').get('en_asset_type')
        }

        return resolve_fields

    def _get_published_main_plate(self, sg_reader, project_id, entity_id, step_bools):
        '''
        Get the main plate from  network storage

        :param sg_reader: sg_reader instance to use for file navigation
        :param project_id: ID number of the current project
        :param entity_id: ID number of the current entity (Shot/Asset)
        '''
        if not project_id or not entity_id:
            self.logger.warning("Could not find Main Plate.")
            return None

        # get main plate for general processes
        if not step_bools or step_bools.get('step_slap_comp') is False:
            published_main_plate = sg_reader.get_pushlished_file(
                project_id,
                "Main Plate",
                "Shot",
                entity_id=entity_id,
                get_latest=True
            )
            self.logger.info("Got main plate of entity %s - %s" % (str(entity_id), published_main_plate))
            return published_main_plate

    def _get_extra_templates(self, item):
        """
        Get assorted templates for assigning input/output locations
        :param item: the collector item for property assignment
        """
        publisher = self.parent

        # find default templates
        # static templates
        nuke_review_template = publisher.engine.get_template_by_name("nuke_dailies_default_json")
        alembic_json_template = publisher.engine.get_template_by_name("alembic_dailies_default_json")

        # field-based templates
        alembic_output_template = publisher.engine.get_template_by_name('alembic_render_json')

        # templates for both shots and assets
        entity_type = item['type'].lower()
        info_json_template = publisher.engine.get_template_by_name('%s_dailies_json_file' % entity_type)
        workfiles_template = publisher.engine.get_template_by_name('nuke_{}_workfiles_location'.format(entity_type))
        qt_template = publisher.engine.get_template_by_name('resolve_{}_review'.format(entity_type))
        qt_template_secondary = publisher.engine.get_template_by_name('resolve_{}_review_secondary'.format(entity_type))

        # find templates for the correct entity type
        if item['type'].lower() == "shot":
            temp_root_template = publisher.engine.get_template_by_name("shot_render_root")
            review_process_json_template = publisher.engine.get_template_by_name("shot_dailies_json")
            alembic_output_template = publisher.engine.get_template_by_name('alembic_shot_dailies_json')
        else:
            temp_root_template = publisher.engine.get_template_by_name("asset_render_root")
            review_process_json_template = publisher.engine.get_template_by_name("asset_dailies_json")
            alembic_output_template = publisher.engine.get_template_by_name('alembic_asset_dailies_json')

        extra_templates = {
            'nuke_review_template': nuke_review_template,
            'alembic_template': alembic_json_template,
            'alembic_output_template': alembic_output_template,
            'info_json_template': info_json_template,
            'temp_root_template': temp_root_template,
            'workfiles_template': workfiles_template,
            'review_process_json_template': review_process_json_template,
            'qt_template': qt_template,
            'qt_template_secondary': qt_template_secondary,
        }

        return extra_templates

    def _apply_templates(self, item):
        """
        Assign paths based on returns from _get_extra_templates and check path validity

        :param item: the collector item for property assignment
        """
        templates = item.get_property('extra_templates')
        resolve_fields = item.get_property('resolve_fields')

        temp_root = templates['temp_root_template'].apply_fields(resolve_fields)
        copy_dir = resolve_fields.copy()
        copy_dir.update({"name": "slapComp"})
        workfiles_directory = templates['workfiles_template'].apply_fields(copy_dir)

        # these need no fields, we can do them just once
        fields = {}
        nuke_review_file = templates['nuke_review_template'].apply_fields(fields)
        review_process_json = templates['review_process_json_template'].apply_fields(fields)
        alembic_json_template = templates['alembic_template'].apply_fields(fields)
        self.logger.info('nuke review %s' % nuke_review_file)
        self.logger.info('process review %s' % review_process_json)
        self.logger.info('alembic json %s' % alembic_json_template)

        job_file_dir = os.path.join(temp_root, "deadline", "submission")

        template_paths = {
            'temp_root': temp_root,
            'job_file_dir': job_file_dir,
            'nuke_review_file': nuke_review_file,
            'review_process_json': review_process_json,
            'workfiles_directory': workfiles_directory,
            'alembic_template': alembic_json_template,
        }

        for i, template_path in template_paths.items():
            template_paths[i] = re.sub("(\s+)", "-", template_path)

        return template_paths

    def _get_process_review_settings(self, item):
        """
        Locates a JSON file based on templates and converts it to a dictionary

        :param item: the collector item for property assignment
        """
        json_file = item.get_property('template_paths').get('review_process_json')
        extension = item.get_property('fields').get("extension").lower()

        if (extension in ["mb", "ma"]
        and item.get_property('template').name in ["maya_shot_outsource_workfile",
            "maya_shot_workfiles_location",
            "maya_asset_workfiles_location"]):
            json_file = item.get_property('template_paths').get('alembic_template')

        # self.logger.warning( ">>>>> review_process_json: %s" % json_file )

        if not os.path.exists(json_file):
            raise Exception("Unable to read Json data from file: %s" % json_file)

        file_content = open(json_file, "r")
        file_str = file_content.read()
        file_content.close()

        json_data = json.loads(file_str)

        return json_data

    def _json_properties(self, item):
        """
        Collects and assigns properties to a dictionary that will be written to a JSON.
        This JSON dictates the settings for Deadline jobs.

        :param item: the collector item for property assignment
        """
        json_properties = item.get_property('review_process_json', {}).copy()
        templates = item.get_property('extra_templates')
        codecs = self.codec_info
        entity_info = item.get_property('entity_info', {})
        resolve_fields = item.get_property('resolve_fields').copy()

        ### FIXME ###
        # A kludge to catch 3DE renders and assign their pass name
        # Catch path template name
        switch_3de = {
            "3dequalizer_playblast_cones_publish": "cones",
            "3dequalizer_playblast_wire_publish": "wire",
        }
        # assign corresponding value to tech_pass
        # so it is correctly incorporated into other paths
        if item.get_property('template').name in switch_3de.keys():
            resolve_fields.update(dict(
                tech_pass = switch_3de.get(item.get_property('template').name)
            ))

        # Render json
        global_json_file = templates['info_json_template'].apply_fields(resolve_fields)
        global_json_file = re.sub("(\s+)", "-", global_json_file)
        json_properties['global_settings']['global_json_file'] = global_json_file
        self.logger.warning("Outputting JSON file to: %s" % json_properties['global_settings']['global_json_file'])

        # Alembic json
        alembic_json_file = templates['alembic_output_template'].apply_fields(resolve_fields)
        alembic_json_file = re.sub("(\s+)", "-", alembic_json_file)
        json_properties['global_settings']['alembic_json_file'] = alembic_json_file

        # set primary or secondary
        process_type = item.get_property('step').get('step_review_level').lower()

        process_dict = json_properties[process_type]
        process_jobs = process_dict['deliverables']

        template_paths = item.get_property('template_paths')

        # collect values and append them to the appropriate settings dictionary
        for job, details in process_jobs.items():
            job_name = str(job)
            current_process = details
            process_config = current_process.get('process_config') or {}
            nk_config = current_process.get('nk_config') or {}
            dl_config = current_process.get('dl_config') or {}

            resolve_fields.update({'process': job_name})

            if process_config.get('plugin_template') and self.project_info.get('pr_root'):
                review_script_path = os.path.join(self.project_info['pr_root'][system_root_variable],
                    process_config['plugin_template'])
                review_script_path = os.path.normpath(review_script_path)
            else:
                review_script_path = template_paths.get('nuke_review_file')

            self.logger.info("%s using nuke template: %s" % (job_name, review_script_path))

            review_output = templates['qt_template'].apply_fields(resolve_fields)

            output_root = os.path.split(review_output)[0]
            output_main = os.path.split(review_output)[1]

            # set temp_root here because it's used in a lot of places
            temp_root = template_paths.get('temp_root')

            dl_root = os.path.join(temp_root, "deadline")
            nuke_out_root = os.path.join(dl_root, "%s_%s.nk")
            nuke_out_script = nuke_out_root % (
                re.sub("(\s+)", "-", item.get_property('version_data')['code']), job_name)

            # check for .job file root and create it if missing
            dirname = os.path.join(temp_root, "deadline", job_name)

            version_name = item.get_property('version_data').get('code')
            basename = "%s_%s" % (version_name, job_name)
            variable_path = os.path.join(dirname, basename)

            job_info_file = "%s_job_info.job" % variable_path
            plugin_info_file = "%s_plugin_info.job" % variable_path

            lens_format = item.get_property('lens')
            if not lens_format:
                self.logger.warning("No lens entity available, falling back to Camera entity")
                lens_format = item.get_property('camera')

            # process_config from item info
            user = self.user_info.get('login')
            if user:
                user = user.split("@")[0]
            vendor = item.get_property('vendor')
            script_file = json_properties['global_settings']['script_file']
            correx_file = json_properties['global_settings'].get('correx_file')
            sg_temp_root = temp_root.replace("\\", "/")

            # nk_config from item info
            cam_transform_switch = lens_format.get('lens_io_transform_switch', 0)
            if not item.get_property('process_plugin_info').get('outsource'):
                if nk_config.get('cam_transform_switch') or not cam_transform_switch:
                    self.logger.warning(">>>>> Defaulting to script preset cam_transform_switch...")
                else:
                    current_process['nk_config'].update({
                        "cam_transform_switch": {"which": cam_transform_switch},
                    })

            # plugin_template = review_script_path.replace("\\", "/")
            plugin_out_script = nuke_out_script
            slate_enabled = self.project_info.get('pr_review_qt_slate')
            burnin_enabled = self.project_info.get('pr_review_burn_in')

            # dl_config from item info
            batch_name = (item.get_property('version_data')['code'] + "_submit")
            job_name = ("%s_%s" % (item.get_property('version_data')['code'], job_name))
            content_output_file = output_main
            content_output_file_total = output_main
            content_output_root = output_root or ""
            frame_range = item.get_property('frame_range')
            # FIXME will this invalidate thumbnail dependency?
            job_dependencies = ""

            slate_frames = self.project_info.get('pr_delivery_slate_count')
            if not slate_frames:
                slate_frames = 0

            # default frame range to 1-1 because we need something
            head_in = 1
            tail_out = 1
            if frame_range:
                head_in = int(frame_range.split('-')[0])
                tail_out = int(frame_range.split('-')[-1])

            slate_range = "%s-%s" % ((head_in - slate_frames), tail_out)

            set_software = item.get_property('set_software', {})
            item_software = set_software.get('products')

            publish_file_type = dl_config.get('publish_file_type')
            if item_software == "Maya" and item.get_property('step')['id'] == 4:
                self.logger.warning('Changing publish file type from %s to Alembic Cache' % publish_file_type)
                publish_file_type = "Alembic Cache"

            current_process['process_config'].update({
                # Validate the plugin settings against json presets
                "dcc": current_process['process_config'].get('dcc', item_software),
                "dcc_exe": current_process['process_config'].get('dcc_exe', set_software.get(system_path_variable)),
                "dcc_version": current_process['process_config'].get('dcc_version', set_software.get('version_names')),
                # Everything else gets regular assignments
                "review_output": review_output,
                "user": user,
                "vendor": vendor,
                "script_file": script_file,
                "correx_file": correx_file,
                "sg_temp_root": sg_temp_root,
            })

            # General Nuke Settings
            current_process['nk_config'].update({
                "plugin_template": review_script_path,
                "format": lens_format,
                "plugin_out_script": plugin_out_script,
                "slate_enabled": slate_enabled,
                "burnin_enabled": burnin_enabled,
            })

            ### Node-specific Nuke Settings ###
            # General Script Settings
            # make sure read, write, and color nodes exist so we don't overwrite settings
            for node in ["render_read", "entity_ccc", "sequence_ccc", "entity_lut", "final_write"]:
                if not current_process['nk_config'].get(node):
                    current_process['nk_config'][node] = {}

            # Main Read
            current_process['nk_config']['render_read'].update({
                'knob_order': ['file'],
                'file': item.get_property('padded_item_name'),
                'first': head_in,
                'last': tail_out,
                })

            # Shot CCC
            shot_ccc_file = ""
            entity_ccc = entity_info.get('sg_entity_ccc')
            if entity_ccc is not None:
                shot_ccc_file = entity_ccc.get(system_root_variable).replace("\\", "/")

            current_process['nk_config']['entity_ccc'].update({
                'knob_order': ['file'],
                'read_from_file': True,
                'file': shot_ccc_file,
                'disable': shot_ccc_file == "",
            })
            # seq CCC
            seq_ccc_file = ""
            sequence_ccc = entity_info.get('sg_sequence_ccc')
            if sequence_ccc is not None:
                seq_ccc_file = sequence_ccc.get(system_root_variable).replace("\\", "/")

            current_process['nk_config']['sequence_ccc'].update({
                'knob_order': ['file'],
                'read_from_file': True,
                'file': seq_ccc_file,
                'disable': seq_ccc_file == "",
            })

            # Shot Cube
            vfield_file = ""
            vfield = entity_info.get('sg_entity_lut')
            if vfield is not None:
                vfield_file = vfield.get(system_root_variable).replace("\\", "/")

            current_process['nk_config']['entity_lut'].update({
                'knob_order': ['vfield_file'],
                'vfield_file': vfield_file,
                'disable': vfield_file == "",
            })

            ### SLATE Group ###
            # Vendor
            set_vendor = item.get_property('vendor')
            if not set_vendor:
                set_vendor = self.user_info.get('name')

            # Slate Node
            current_process['nk_config']['HOUSE_SLATE'] = {
                'show': self.project_info.get('name'),
                'shot': entity_info.get('code'),
                'version': version_name,
                'vendor': set_vendor,
                'start_frame': head_in,
                'end_frame': tail_out,
                'lens': entity_info.get('en_lens_info'),
                'notes': None}

            ### OUTPUT ###
            current_process['nk_config']['final_write'].update({
                'knob_order': ['file'],
                'file': review_output.replace('\\', '/'),
            })

            current_process['dl_config'].update({
                "batch_name": batch_name,
                "job_name": job_name,
                "output_file": content_output_file,
                "output_file_ext": "",
                "content_output_file_total": content_output_file_total,
                "output_root": content_output_root,
                "publish_file_type": publish_file_type,
                "frame_range": slate_range,
                "job_dependencies": job_dependencies,
                "job_info_file": job_info_file,
                "plugin_info_file": plugin_info_file,
                "department": item.get_property('step').get('source_dept'),
            })

            # self.logger.warning(">>>>> job_info_file: %s" % job_info_file)

        process_dict['project_info'] = {i: self.project_info[i] for i in self.project_info
                                        if i != 'formats'}

        # Re-compile step, task, camera, and entity info into a single dictionary
        process_dict['entity_info'] = {
            'task_info': {},
            'step_info': {},
            'lens_info': {},
            'camera_info': {},
        }
        for key, value in entity_info.items():
            process_dict['entity_info'][str(key)] = value

        for key, value in item.get_property('task').items():
            process_dict['entity_info']['task_info'][str(key)] = value

        for key, value in item.get_property('step').items():
            process_dict['entity_info']['step_info'][str(key)] = value

        for key, value in item.get_property('lens').items():
            process_dict['entity_info']['lens_info'][str(key)] = value

        for key, value in item.get_property('camera').items():
            process_dict['entity_info']['camera_info'][str(key)] = value

        # as a quick final step just append the primary/secondary process dictionary to the item properties
        item.properties['process_dict'] = process_dict

        return json_properties

    def _get_existing_playlist(self, item):
        """
        Check for an existing Resolve playlist
        """
        # Build playlist name from resolve_fields timestamps
        resolve_fields = item.get_property('resolve_fields')
        playlist_name = "%s%s%s_Resolve_Review_%s" % (
                "%04d" % (resolve_fields.get('YYYY')),
                "%02d" % (resolve_fields.get('MM')),
                "%02d" % (resolve_fields.get('DD')),
                str(resolve_fields.get('ampm')))

        ctx = self.parent.engine.context
        project = {'type' : 'Project', 'id' : ctx.project['id']}
        filters =[
            ['project', 'is', project],
            ['code', 'is', playlist_name]
            ]
        fields = ['code', 'id', 'versions']

        existing_playlist = {
            "playlist_data": {
                "project": project,
                "code": playlist_name,
                "pl_status": "rsv"
            }
        }

        self.logger.debug("Looking for Playlist: %s" % playlist_name)
        search_playlist = self.parent.shotgun.find_one(
            "Playlist",
            filters,
            fields
            )

        if not search_playlist:
            self.logger.info("Creating Playlist...")
            search_playlist = self.parent.shotgun.create(
                "Playlist", 
                existing_playlist.get('playlist_data'),
                return_fields = fields
                )

        if search_playlist:
            existing_playlist['playlist'] = search_playlist

        self.logger.info("Playlist: %s" % existing_playlist)
        return existing_playlist

    def _task_fields(self, curr_fields):
        '''
        Generate a list of fields to search for in SG

        :param curr_fields: info derived from the path and used for specificity
        '''
        # default field
        search_fields = [
            "entity",
        ]

        # step fields
        search_fields.extend([
            "step.Step.id",
            "step.Step.code",
            'step.Step.source_dept',
            'step.Step.step_publish_to_shotgun',
            'step.Step.step_version_for_review',
            'step.Step.step_slap_comp',
            'step.Step.step_review_level',
            'step.Step.entity_type',
        ])

        # entity fields
        entity_type = curr_fields['type']
        if entity_type == "Shot":
            search_fields.extend([
                "entity.Shot.code",
                "entity.Shot.id",
                "entity.Shot.type",
                "entity.Shot.description",
                "entity.Shot.created_by",
                "entity.Shot.dcc_status",
                "entity.Shot.sg_entity_lut",
                "entity.Shot.sg_entity_ccc",
                "entity.Shot.sg_sequence_ccc",
                "entity.Shot.en_episode",
                "entity.Shot.en_shot_audio",
                "entity.Shot.en_project_name",
                "entity.Shot.en_plates_processed_date",
                "entity.Shot.en_shot_ocio",
                "entity.Shot.en_without_ocio",
                "entity.Shot.en_head_in",
                "entity.Shot.en_tail_out",
                "entity.Shot.en_lens_info",
                "entity.Shot.en_plate_proxy_scale",
                "entity.Shot.en_frame_handles",
                "entity.Shot.en_vfx_work",
                "entity.Shot.en_work_scope",
                "entity.Shot.en_editorial_notes",
                "entity.Shot.en_sequence"
                "entity.Shot.en_main_plate",
                "entity.Shot.en_latest_ver",
                "entity.Shot.en_latest_client_ver",
                "entity.Shot.en_gamma",
                "entity.Shot.en_target_age",
                "entity.Shot.en_shot_transform",
                "entity.Shot.en_main_plate_cam",
                "entity.Shot.en_main_plate_cam.Camera.code",
                "entity.Shot.en_main_plate_cam.Camera.sg_format_width",
                "entity.Shot.en_main_plate_cam.Camera.sg_format_height",
                "entity.Shot.en_main_plate_cam.Camera.sg_pixel_aspect_ratio",
                "entity.Shot.en_main_plate_cam.Camera.sg_io_incoming_transform_switch",
                "entity.Shot.en_lens.CustomNonProjectEntity09",
                "entity.Shot.en_lens.CustomNonProjectEntity09.code",
                "entity.Shot.en_lens.CustomNonProjectEntity09.sg_category",
                "entity.Shot.en_lens.CustomNonProjectEntity09.sg_format_width",
                "entity.Shot.en_lens.CustomNonProjectEntity09.sg_format_height",
                "entity.Shot.en_lens.CustomNonProjectEntity09.sg_pixel_aspect_ratio",
                "entity.Shot.en_lens.CustomNonProjectEntity09.lens_io_transform_switch",
            ])

        elif entity_type == "Asset":
            search_fields.extend([
                "entity.Asset.code",
                "entity.Asset.id",
                "entity.Asset.type",
                "entity.Asset.en_asset_type",
                "entity.Asset.description",
                "entity.Asset.created_by",
                "entity.Asset.dcc_status",
                "entity.Asset.en_head_in",
                "entity.Asset.en_tail_out",
                "entity.Asset.en_lens_info",
                "entity.Asset.en_vfx_work",
                "entity.Asset.en_work_scope",
                "entity.Asset.en_editorial_notes",
                "entity.Asset.en_latest_ver",
                "entity.Asset.en_latest_client_ver"
            ])

        return search_fields

    # #### Retrieved from utils
    def initial_path_info_returns(self, path=None, ignore_folder_list=None, seek_folder_list=None):
        """
        :param path: string, root path of data bundle
        :param seek_folder_list: list, Includes contents of these folders in search return
        :param ignore_folder_list: list, Excludes contents of these folders in search return

        :return path_info: dict of dicts, contains all initial info for further processing
        """
        self.logger.warning(">>>>> Collecting initial_path_info_returns...")
        find_path = path_finder.PathFinder(self.logger)

        # run path_finder
        if ignore_folder_list is None:
            ignore_folder_list = []
        if seek_folder_list is None:
            seek_folder_list = []

        # Always submit a folder path 
        # We can reconstruct the file path if needed
        ext = os.path.splitext(path)[-1]
        if ext:
            finder_path = os.path.dirname(path)
        else:
            finder_path = path

        self.logger.warning(">>>>> Collecting path: %s" % finder_path)
        path_info_returns = find_path.get_folder_contents(
            finder_path,
            ignore_folder_list,
            seek_folder_list,
            file_ext_ignore=["db"],
            legacy=False)
        path_info = {'all_fields': {}, 'path_info_returns': path_info_returns}

        # initialize templates
        tk = sgtk.sgtk_from_path(path)
        root_template = tk.template_from_path(path)
        path_info['all_fields']['root_template'] = root_template

        # Determine if submission is from Outsource
        outsource = False
        if root_template.name in [
            "incoming_outsource_shot_dir_root",
            "incoming_outsource_asset_dir_root"
            ]:
            outsource = True

        if outsource:
            self._initial_outsource(tk, path_info)
            return path_info
        else:
            self._initial_artist(tk, path, path_info)
            return path_info

    def _initial_artist(self, tk, path, path_info):
        """
        Initial processing for Artist submissions
        packages template and software info

        :param tk: toolkit instance, so it doesn't need to be initialized more than once
        :param path: string, single item path, only needed for workfiles
        :param path_info: list of dicts, items from our path_finder to process

        :return path_info: list of dicts, contains updated dictionaries with template info
        """
        self.logger.warning("Proceeding as Artist submission...")
        path_info_returns = path_info.get('path_info_returns')

        # Check for workfiles
        # Because we always submit folders to path_finder, but only want 1 script file
        # Workfiles need an extra step to reduce the list in order to process correctly
        workfile_templates = [
            "houdini_shot_workfiles_location",
            "houdini_asset_workfiles_location",
            "maya_shot_workfiles_location",
            "maya_asset_workfiles_location",
            "nuke_shot_workfiles_location",
            "nuke_asset_workfiles_location",
            "psd_asset_workfiles_location",
            "psd_shot_workfiles_location",
        ]
        
        if path_info['all_fields']['root_template'].name in workfile_templates:
            self.logger.warning(">>>>> Workfile detected, proceeding with single file...")
            matched_file = [
                i for i in path_info_returns if i.get('padded_item_name') == path
                ]
            path_info_returns = matched_file

        for item in path_info_returns:
            # determine if submission is a single file (frame or script)
            # single frames will assess with hash padding, so there needs to be an extra check
            item['single'] = self.is_single(item)

            # NOTE: The process here is identical across both processes
            # But has been itematized to make future edits easier

            # Get the path to feed to collect_file/collect_folder 
            self.get_processing_path(item)
            # Use the appropriate path to define the SG template
            self.define_template(tk, item.get('padded_item_name'), item)
            # Extract the fields from the template
            self.template_fields(item)
            # Use the template fields to determine if the entity is a Shot or an Asset
            self.define_shot_asset(item)

            # Determine the appropriate software
            process_info = {
                "outsource": False,
                "software": "Nuke",
            }

            if item['base_template'].name in [
                "maya_shot_workfiles_location",
                "maya_asset_workfiles_location",
            ]:
                process_info['software'] = "Maya"

            item['process_plugin_info'] = process_info

            # upadate all_info with any outstanding key:value pairs
            for field_key, field_val in item['fields'].items():
                if not path_info['all_fields'].get(field_key):
                    path_info['all_fields'][field_key] = field_val

        return path_info

    def _initial_outsource(self, tk, path_info):
        """
        Initial processing for Outsource submissions
        packages template and software info

        :param tk: toolkit instance, so it doesn't need to be initialized more than once
        :param path_info: list of dicts, items from our path_finder to process

        :return path_info: list of dicts, contains updated dictionaries with template info
        """
        self.logger.warning("Proceeding as Outsource submission...")

        for item in path_info.get('path_info_returns'):
            # determine if submission is a single file (frame or script)
            # single frames will assess with hash padding, so there needs to be an extra check
            item['single'] = self.is_single(item)

            # NOTE: The process here is identical across both processes
            # But has been itematized to make future edits easier

            # Get the path to feed to collect_file/collect_folder 
            self.get_processing_path(item)
            # Use the appropriate path to define the SG template
            self.define_template(tk, item.get('padded_item_name'), item)
            # Extract the fields from the template
            self.template_fields(item)
            # Use the template fields to determine if the entity is a Shot or an Asset
            self.define_shot_asset(item)

            # Determine the appropriate software
            process_info = {
                "outsource": True,
                "software": "Nuke",
            }

            if item['base_template'].name in [
                "maya_shot_outsource_workfile",
                "maya_asset_outsource_work_file",
            ]:
                process_info['software'] = "Maya"
                process_info['process'] = "Alembic"

            item['process_plugin_info'] = process_info

            # upadate all_info with any outstanding key:value pairs
            for field_key, field_val in item['fields'].items():
                if not path_info['all_fields'].get(field_key):
                    path_info['all_fields'][field_key] = field_val

        return path_info

    def is_single(self, item):
        """
        identify item as single file, or folder item

        :param item: Dictionary item to process

        :return booleon:
        """
        single = False
        if item['file_range'] == 0:
            single = True
        elif item['file_range'].split('-')[0] == item['file_range'].split('-')[-1]:
            single = True
        return single
    
    def get_processing_path(self, item):
        """
        :param item: Dictionary item to process

        :return item: Dictionary with Template info
        """

        # Establish path for collector processing
        padded_path = item.get('padded_item_name')
        if not item.get('single'):
            item['directory'] = os.path.dirname(padded_path)
        elif not item.get('hashed_pad'):
            item['full_path'] = item['padded_item_name']
        else:
            item['full_path'] = re.sub(
                item['hashed_pad'], 
                str(item['file_range']).split('-')[0], 
                padded_path
            )

        self.logger.info('PATH IS: %s' % padded_path)

        return item
    
    def define_template(self, tk, path, item):
        """
        Use path to identify template

        :param tk: Toolkit instance so we don't need to reintance it
        :param path: String path to get template
        :param item: Dictionary item to process

        :return item: Dictionary with Template info
        """
        template_path = path
        self.logger.info('Finding template from path: %s' % template_path)
        work_template = tk.template_from_path(template_path)
        attempts = 0

        # if no work template is found, make two attempts to find a fallback using the directory
        # The limit is two because templates become uninformative beyond that point
        if not work_template:
            for attempt in range(2):
                template_path = os.path.dirname(template_path)
                self.logger.warning(">>>>> No work_template, attempting fallback %s wih path %s..." % (
                    str(attempt+1),
                    template_path
                    ))
                work_template = tk.template_from_path(template_path)
                attempts+=1

                if not work_template:
                    continue
                else:
                    break

        # We need a template so try to whittle the path down until one registers
        # NOTE This is wildly unsafe, but it hasn't broken yet...
        if not work_template:
            self.logger.warning(">>>>> Could not find template for %s. Continuing..." % template_path)
            return item

        self.logger.info("After {attempts} tries, using template path: {path}".format(
            attempts=attempts,
            path=template_path
            )
        )
        
        item['template_path'] = template_path
        item['base_template'] = work_template
        self.logger.info('TEMPLATE NAME IS: %s' % work_template.name)

        return item

    def template_fields(self, item):
        """
        Use item to extract fields from template
        
        :param item: Dictionary item to process

        :return item: Dictionary with extracted template field info
        """
        curr_fields = item['base_template'].get_fields(item['template_path'])
        item['fields'] = curr_fields
        if not curr_fields.get("extension"):
            ext = os.path.splitext(item['padded_item_name'])[-1]
            ext = ext.lstrip(".")
            item['fields'].update({"extension": ext})

        item['fields']['task_name'] = item['fields']['task_name'].lower()

        return item

    def define_shot_asset(self, item):
        """
        Use item fields to identify if the entity is a Shot or an Asset
        
        :param item: Dictionary item to process
        
        :return item: Dictionary with correct entity type added to template fields
        """
        if "Shot" in item['fields']:
            item['fields'].update({
                'Entity': item['fields']['Shot'],
                'type': "Shot"
            })
        else:
            item['fields'].update({
                'Entity': item['fields']['Asset'],
                'type': "Asset"
            })

        return item
    
    def _get_outsource_paths(self, item):
        """
        Remaps paths from outsource submissions to
        1) Copy the path from admin/incoming/outsource to the correct
        internal filesystem location
        2) Publish the remaped path

        :param item: the collector item for property assignment

        :return outsource_paths: Dictionary with remaped oursource/copy paths
        """
        outsource_paths = {
            "origin_path": item.get_property('padded_item_name'),
        }

        # Identify Outsource object type
        fields = item.get_property('fields')
        if not fields:
            self.logger.warning(">>>>> No fields to process, returning...")
            return outsource_paths
        
        ext = fields.get("extension")
        # TODO This is an unacceptible fudge
        # Find the real source of ext and apply it, or replace the template field correctly. 
        fields.update({"ext": ext})

        # reject files without homes in file system
        # TODO Find where these files should live
        reject = ["exr"]
        if ext in reject:
            self.logger.info("Bypassing %s file. No storage specified." % ext)
            return

        # Find templates for artist filesystem locations
        copy_template = None
        if ext == "ma":
            copy_template = self.parent.engine.get_template_by_name('maya_shot_workfiles_location')
        elif ext == "3de":
            copy_template = self.parent.engine.get_template_by_name('3dequalizer_shot_workfiles_location')
        elif ext == "abc":
            copy_template = self.parent.engine.get_template_by_name('incoming_outsource_cam_copy')
        elif fields.get("outsource_render"):
            outsource_render = fields.get("outsource_render")
            if outsource_render in ["renders", "UD"]:
                copy_template = self.parent.engine.get_template_by_name('incoming_outsource_seq_copy')
            elif outsource_render == "nuke":
                if ext == "nk":
                    copy_template = self.parent.engine.get_template_by_name('nuke_shot_workfiles_location')

        if not copy_template:
            self.logger.warning("Could not locat template to construct paths for file copy. Bypassing...")
            return outsource_paths

        # Build artist filesystem path
        copy_path = ""
        if copy_template:
            copy_path = copy_template.apply_fields(fields)
            outsource_paths.update({"copy_template": copy_template})

        if copy_path:
            outsource_paths.update({"copy_path": copy_path,})
        else:
            self.logger.warning("Could not construct paths for file copy. Bypassing...")
            return outsource_paths

        # Convert path #### value to %0ND value
        sub_path = self._percent_padded_path(outsource_paths.get('copy_path'), item)
        outsource_paths.update({
        "copy_path": sub_path,
        })

        self.logger.info("outsource_paths: %s" % outsource_paths)

        # Remap paths to copy/publish copied files.
        item.properties['path'] = outsource_paths.get('copy_path')
        item.properties['padded_item_name'] = outsource_paths.get('copy_path')

        if item.get_property('sequence_paths'):
            dirname = os.path.dirname(outsource_paths.get('copy_path'))
            self.logger.warning(">>>>> outsource_dir: %s" % dirname)
            item.properties['sequence_paths'] = [
                os.path.join(dirname, os.path.basename(i)) for i in item.properties['sequence_paths']
            ]

        self.logger.info("Remapping input path to: %s" % item.get_property('padded_item_name'))

        return outsource_paths

    def _percent_padded_path(self, path, item):
        """
        Generate a path using %Nd padding

        :param path: String of original input path
        :param item: Dictionary item to process

        :return percent_path: String path with %Nd padding if padding is applicable
        """
        
        percent_path = path
        frame_range = item.get_property('frame_range')
        if frame_range:
            tail = str(frame_range).split("-")[-1]
            fill = "%{fdigit}d".format(fdigit=str(len(tail)).zfill(2))

            sub_path = re.sub("#+", fill, path)
            if sub_path:
                percent_path = sub_path

        return percent_path

    def _get_image_extensions(self):

        if not hasattr(self, "_image_extensions"):

            image_file_types = ["Photoshop Image", "Rendered Image", "Texture Image", "BGEO"]
            image_extensions = set()

            for image_file_type in image_file_types:
                image_extensions.update(
                    self.common_file_info[image_file_type]["extensions"]
                )

            # get all the image mime type image extensions as well
            mimetypes.init()
            types_map = mimetypes.types_map
            for (ext, mimetype) in types_map.items():
                if mimetype.startswith("image/"):
                    image_extensions.add(ext.lstrip("."))

            self._image_extensions = list(image_extensions)

        return self._image_extensions