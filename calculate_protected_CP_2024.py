"""
Conservation Gaps Analysis
This analysis calculates the amount of 'Conservation Priorities' protected by
conservation areas in the Northern Shelf Bioregion with the option to consider
the presence and impact of human activities.
"""

# Standard library imports
import csv
from datetime import datetime as dt
import logging
import logging.config
import os
import re

# Third party imports
import arcpy
import pandas as pd
from pathlib import Path


#######################################################################
### DIRECTORY CONFIGURATIONS ###
#######################################################################
#
# This section detects the script's working directory on the user's
# computer and sets the relative paths to the input and output files/
# data used in the script. These relative paths are used in the
# "CONFIGURABLE VARIABLES" section to build the file references.
#
##

# Define script location (root-level working directory)
dir_root = Path(__file__).parent
print(dir_root)

# Define relative paths to the various files used in the script.
# Spatial input data
dir_aprx = Path("aprx/CGA_QuickStart.aprx")
dir_spatial_working_gdb = Path("spatial/working_TEMP")

# Tabular input data
dir_input_imatrix = Path("input/interactionmatrix_20210531.csv")
dir_input_inclusion_matrix = Path("input/MPATT_Spatial_P3_CGAAssess_20220616.csv")
dir_input_cp_overlap = Path("input/cpOverlap_rev.csv")
dir_input_eco_uids = Path("input/mpatt_eco_UID-simple_20210601.csv")

# Output data
dir_output_table1 = Path("output/table1.csv")
dir_output_table1join = Path("output/table1_joined.csv")
dir_output_table2 = Path("output/table2.csv")
dir_output_table3 = Path("output/table3.csv")
dir_output_table4 = Path("output/table4.csv")


#######################################################################
### CONFIGURABLE VARIABLES ###
#######################################################################
#
# This section sets the references to all files and configurations
# required for the script. The input/output file references point to
# the Quick Start datasets by default. Other variables can be modified
# to change the behaviour of the script.
#
##

#######################################################################
# Input/output files and related configs

### source_aprx and source_mapframe_name ###
#
# File path to the Esri .aprx file and the map frame name containing all
# spatial layers to be used in the analysis.
#
##
source_aprx = dir_root / dir_aprx
source_mapframe_name = "Layers"


### working_gdb_folder ###
#
# The folder path where temporary files will be stored. The script
# will create a new geodatabase with a unique name. The script will
# delete the database at the end if cleanUpTempData is set to True.
# If an error is thrown while running the script, the gdb may not be deleted.
#
##
working_gdb_folder = dir_root / dir_spatial_working_gdb


### imatrix_path ###
#
# The path to the interaction matrix CSV file listing the consequence score for
# each combination of eco feature (CP) and HU feature. The second column should be
# the eco feature dataset name. The fourth column should be the activity
# name. The sixth column is the consequence score.
#
# For example a row reading like this:
# [..., eco_inverts_clamrazor_ia_d, ..., BeachSeeding, ..., Minor Negative]
#
# This CSV should have a header row. It will be discarded when the CSV is read in
# but if it is missing the first row of data will not be processed.
#
##
imatrix_path = dir_root / dir_input_imatrix


### inclusion_matrix_path ###
#
# NOTE: The term "inclusion matrix" is an older term for "assessment matrix".
#
# The path to the inclusion matrix CSV file listing which activities are
# allowed/restricted in an MPA based on management intent. The first row
# starting with the second column should be the HU feature class names. The
# first column starting with the second row should contain MPA names.
#
# Where these MPAs and HU names intersect should be one of the following:
#   O: This activity is not a concern and/or is permitted to occur
#   C: This activity is not restricted in the MPA
#   X: This activity is restricted from occurring in the MPA
#   na: Not applicable (i.e., activity would not occur in that location)
# Any other value will be treated as blank and the script will determine
# inclusion based on spatial calculations.
#
# The script's method of handling these values can be further configured
# by setting the override_y and override_n variables below.
#
##
inclusion_matrix_path = dir_root / dir_input_inclusion_matrix


### cpOverlap (Conservation Priority area overlap) ###
#
# Each conservation priority (eco feature) is intersected with each subregion
# and ecosection to get the total area of the CP that falls in each region and
# section. A dictionary is created to hold these values and can be reused in
# runs of the CGA to cut down on processing time.
#
# cpOverlap_newDict
# If True, the script will build a completely new dictionary. This may be
# advisable if there is uncertainty about the status of the script and data.
# If False, the script will check if a feature exists in the existing
# dictionary, and if not, will complete an intersect and add the feature.
#
# cpOverlap_DictPath
# The path to the current CSV file containing the CP overlap areas.
#
# For repetitive runs of the CGA where the CP inputs don't change, it will save
# time to not have to do an intersect and dissolve on every CP on every run.
# Keep in mind that if just adding data and not changing existing datasets,
# cpOverlap_newDict can remain set to False and the new data will be appended
# to the dictionary.
#
##
cpOverlap_newDict = False
cpOverlap_DictPath = dir_root / dir_input_cp_overlap


### ecoUIDs_path (Eco UIDs CSV file) ###
#
# Input file that will be joined to the Table 1 output. Includes the CP
# UIDs ("eco features") as well as additional related fields.
#
##
ecoUIDs_path = dir_root / dir_input_eco_uids


### Output CSV paths ###
#
# The paths to the output CSV files produced by the script.
# This section also includes the reference to an input file (ecoUIDs_path),
# which is joined to Table 1.
#
# Table 1 (output1_path)
# Lists amount of each CP (eco feature) in each MPA zone, divided into
# subregions and ecozones if zone overlaps multiple. Amounts are presented
# as proportion of total (scaled/unscaled) for the Northern Shelf Bioregion
# (NSB) and value (scaled/unscaled).
#
# Table 1 joined (output1join_path)
# Includes the contents of Table 1 joined with eco/CP UIDs (ecoUIDs_path).
#
# Table 2 (output2_path)
# Lists CPs by ecosection/subregion, including their proportion, original
# areas, and protected areas.
#
# Table 3 (output3_path)
# Sliver threshold table containing MPAs, CP/HU layers, and the percentage
# of area overlap between them.

# Table 4 (output4_path)
# Lists the CP and HU interactions by MPA.
#
##
output1_path = dir_root / dir_output_table1
output1join_path = dir_root / dir_output_table1join
output2_path = dir_root / dir_output_table2
output3_path = dir_root / dir_output_table3
output4_path = dir_root / dir_output_table4


#######################################################################
# Other configurable variables

### print_status & detailed_status ###
#
# If True, will print various status messages to the standard output
# (stdout) while the script runs.
# If False, will not print any status messages to the stdout, but errors/
# exceptions will still appear in the standard error output stream (stderr).
#
##
print_status = True
detailed_status = True


### cleanUpTempData ###
#
# If True, will delete temporary data after it has been used.
# Set to False to retain the temp data after the script has run.
# It may not be advisable to set as False if running the script
# with a large dataset (e.g., completing a "full run") because a
# very large amount of temp data will be produced.
#
##
cleanUpTempData = False


### sr_code ###
#
# The spatial reference code (WKID) that will be used for projections
# and calculations.
#
##
sr_code = 3005 # NAD_1983_BC_Environment_Albers


### cp_presence_threshold, hu_presence_threshold, & layer_presence_threshold_file ###
#
# The spatial threshold percent over which a layer is considerd present within
# an MPA. This is defined as a decimal number from 0 - 1 (eg. 0.05 => 5%).
# Optionally layer_presence_threshold_file can be defined as the path to a CSV
# file defining these thresholds for each layer. The first column is the name of
# the layer and the second is the threshold percentage as a decimal number
# between 0 and 1. If a layer is not present in the CSV then the appropriate
# value will be used from cp_presence_threshold or hu_presence_threshold. If
# layer_presence_threshold_file is set to None then only those defined variables
# are used. This CSV should NOT have a header.
#
##
cp_presence_threshold = 0.0
hu_presence_threshold = 0.01
#
# NOTE: Custom configuration
# A layer presence threshold file is not typically used. Default value is None.
layer_presence_threshold_file = None


### mpa_name_fields ###
#
# mpa_name_field: The field name of MPA unique identifier in MPA dataset.
# mpa_name_e: The field name of full MPA name in English.
#
##
mpa_name_field = 'UID'
mpa_name_e = 'NAME_E'


### override_y & _n ###
#
# These override variables define how to interpret the presence of an HU
# activity in an MPA when a code exists in the inclusion matrix (O, C, X, na).
#
# override_y
# If False, any HU-MPA combo in the inclusion matrix with codes "O" or "C"
# will be included in an MPA.
# If True, the script will determine inclusion based solely on the spatial
# calculations.
#
# override_n
# If False, any HU-MPA combo in the inclusion matrix with the code "X"
# will not be included in the MPA.
# If True, the script will determine inclusion based solely on the spatial
# calculations.
#
# To complete a "typical" run:
# override_y = False
# override_n = True
# Result: Any HU-MPA combo with "O" or "C" will be considered present even if it
# does not spatially overlap. Any combo with "X" or "na" will only be considered
# present if it spatially overlaps (spatial overlap "overrides" the "X").
#
# To complete a run with the inclusion matrix only and no spatial data (so that the
# inclusion matrix determines the presence of an HU):
# override_y = False
# override_n = False
#
# To complete a run with spatial data, but where a permitted activity is only
# included if it spatially overlaps, and a restricted activity is excluded
# even if it spatially overlaps:
# override_y = True
# override_n = False
# Result: Any HU-MPA combo with "O" or "C" is only considered present in an mpa if it
# spatially overlaps. Any combo with "X" or "na" is considered absent even if it overlaps.
#
##
override_y = False
override_n = True


### complexFeatureClasses ###
#
# A list of strings representing the feature class names of features that
# are too complex to process as is. These features are split into single-part
# features which typically solves processing issues.
#
# For features classes that are split by attribute prior to this script,
# simply include the name up until the "_{value}". It is not necessary
# to enter in every instance of it.
#
##
complexFeatureClasses = ['eco_coarse_bottompatches_polygons_d',
                         'eco_coarse_geomorphicunits_polygons_d',
                         'eco_coarse_coastalclasses_lines_d']


### Special cases (HU datasets) ###
#
# A dictionary of HU datasets that are further split by subtype. For
# instance, there is just one spatial dataset for seine fishing, but in
# the inclusion matrix, it is preferable distinguish between targeted
# species allowed in each MPA (e.g. salmon, herring, sardine). However,
# if an MPA allows more than 1 type, this should only be counted once.
#
##
hu_multiple = {'hu_co_demersalfishing_inverttrapcom_d': {'variants':
                                                   ['hu_co_demersalfishing_inverttrapcom_d_PRAWN',
                                                    'hu_co_demersalfishing_inverttrapcom_d_CRAB']},
              'hu_co_pelagicfishing_purseseine_d': {'variants':
                                                   ['hu_co_pelagicfishing_purseseine_d_SALMON',
                                                    'hu_co_pelagicfishing_purseseine_d_HERRING']},
              'hu_co_pelagicfishing_gillnetscom_d': {'variants':
                                                      ['hu_co_pelagicfishing_gillnetscom_d_HERRING',
                                                       'hu_co_pelagicfishing_gillnetscom_d_SALMON']},
              'hu_co_scubadivefishing_scubadivefishingcom_d': {'variants':
                                                      ['hu_co_scubadivefishing_scubadivefishingcom_d_GSU',
                                                       'hu_co_scubadivefishing_scubadivefishingcom_d_RSU']},
              'hu_rf_demersalfishing_traprec_d': {'variants':
                                                    ['hu_rf_demersalfishing_traprec_d_CRAB',
                                                    'hu_rf_demersalfishing_traprec_d_PRAWN']},
              'hu_rf_scubadivefishing_scubadivefishingrec_d': {'variants':
                                                     ['hu_rf_scubadivefishing_scubadivefishingrec_d_ALL',
                                                      'hu_rf_scubadivefishing_scubadivefishingrec_d_RSU']}}


#######################################################################
# Logging configuration
#
# This logging configuration sets up two distinct logging methods:
# - logger_file: Writes messages to an external log file only (for debugging)
# - logger_multi: Writes messages to the log file and the standard output (stdout)
#
##
dir_logging_conf = Path("logging/logging.conf")
logging_conf_path = dir_root / dir_logging_conf
logging.config.fileConfig(logging_conf_path)

logger_file = logging.getLogger('fileLogger')
logger_multi = logging.getLogger('multiLogger')

logger_multi.info('Starting script...')




#######################################################################
### FUNCTIONS ###
#######################################################################

## calculate_runtime ##
#
# Tracks how long an operation takes to run by calculating the difference
# between the start and end times. Logs the runtime to the log file in ms & sec. 
#
def calculate_runtime(start_time, end_time, operation, layer):
    intersect_runtime_sec = (end_time - start_time).total_seconds()
    intersect_runtime_min = intersect_runtime_sec / 60
    logger_file.debug('Completed %s (layer: %s). Runtime was %s seconds (%s min)', operation, layer, intersect_runtime_sec, intersect_runtime_min)


## fieldExists ##
#
# Checks if a field with a given name exists in the given feature class.
# Returns True or False.
#
def fieldExists(layer, field):

    logger_file.debug('Starting function')

    for field in arcpy.ListFields(layer):
        if field.name == field:
            return True
    return False


## calculateArea ##
#
# Creates a double field in a feature class with the given name and
# populates it with the area of the associated feature.
#
def calculateArea(layer, area_field):

    logger_file.debug('Starting function')

    arcpy.AddField_management(layer, area_field, 'DOUBLE')
    arcpy.CalculateField_management(layer, area_field, '!shape.area!')


## calculateTotalArea ##
#
# Returns the total area of a feature class by summing the values in
# the passed field.
#
def calculateTotalArea(layer, area_field):

    logger_file.debug('Starting function')

    summed_total = 0
    with arcpy.da.SearchCursor(layer, area_field) as cursor:
        for row in cursor:
            summed_total = summed_total + row[0]
    return summed_total


## createMPAdict ##
#
# Returns a dictionary of MPA attributes to use as a lookup reference.
#
# This was implemented because storing attributes in a dictionary was
# easier than carrying all attributes through in the MPA feature class.
#
def createMPAdict(source_aprx, mpa_name_field, mpa_name_e):

    logger_file.debug('Starting function')

    # Get MPA layers
    aprx = arcpy.mp.ArcGISProject(source_aprx).listMaps(source_mapframe_name)[0]
    layers = aprx.listLayers()
    mpa_layers = [lyr for lyr in layers if lyr.isFeatureLayer and lyr.name.startswith('mpatt_mpa')]
    mpa_dict = {}
    for layer in mpa_layers:
        with arcpy.da.SearchCursor(layer, [mpa_name_field,mpa_name_e]) as mpa_cursor:
            for row in mpa_cursor:
                mpa_dict[row[0]] = {}
                mpa_dict[row[0]] = {'name' : row[1]}
    return mpa_dict


## prepareMPAs ##
#
# Processes MPA layer(s) to include additional data needed for the analysis.
# Returns the updated MPA layer.
#
# Details: Gets MPA layer(s) from the APRX (usually only one layer) by
# reading the dataset name. If multiple MPA layers, merges layers into
# one file. Puts all the MPA names into one column (mpa_name_field) and
# calculates the area of each (mpa_area_field). Intersects MPAs with
# subregions and cosections and dissolve by MPAs and ecosections.

# NOTE: Unnecessary functionality
# The script is never usually run with more than one MPA dataset,
# so code pertaining to multiple MPA layers is unnecessary.
#
def prepareMPAs(source_aprx, sr_code, mpa_area_field, mpa_area_attribute_section, final_mpa_fc_name, merged_name_field,
                mpa_name_field, mpa_subregion_field, subregions_ALL, ecosections_layer, mpa_marine_area):

    logger_file.debug('Starting function')

    # Get MPA layers
    aprx = arcpy.mp.ArcGISProject(source_aprx).listMaps(source_mapframe_name)[0]
    layers = aprx.listLayers()
    mpa_layers = [lyr for lyr in layers if lyr.isFeatureLayer and lyr.name.startswith('mpatt_mpa')]

    # Load layers into workspace (and project)
    working_layers = []
    for lyr in mpa_layers:
        arcpy.Project_management(lyr.dataSource, lyr.name,
                                 arcpy.SpatialReference(sr_code))
        working_layers.append(lyr.name)

    # Set up field mappings (need a single consistent name field)
    fm = arcpy.FieldMappings()
    for lyr in working_layers:
        fm.addTable(lyr)
    fmap = arcpy.FieldMap()
    for lyr in working_layers:
        name_field = None
        for field in arcpy.ListFields(lyr):
            if field.name == mpa_name_field:
                name_field = field.name
                break
        if name_field is None:
            raise ValueError('MPA Layer: {0} does not have field name in mpa_name_field'.format(lyr))
        fmap.addInputField(lyr, name_field)
    nf = fmap.outputField
    nf.name = merged_name_field
    fmap.outputField = nf
    fm.addFieldMap(fmap)
    for field in fm.fields:
        if field.name != merged_name_field and field.name != mpa_marine_area:
            fm.removeFieldMap(fm.findFieldMapIndex(field.name))

    # Perform merge and calculate area field
    arcpy.Merge_management(working_layers, "mpas_merged", fm)

    # Clean up the individual MPA files
    if cleanUpTempData:
        for layer in working_layers:
            arcpy.Delete_management(layer)

    # Determine which subregion each MPA is in
    # Add field 'mpa_subregion_field'
    arcpy.AddField_management("mpas_merged", mpa_subregion_field,"TEXT")

    # Intersect MPAs and subregions
    intersect_start_time = dt.now()
    arcpy.analysis.PairwiseIntersect(["mpas_merged",subregions_ALL], "mpa_sub_intersect", "NO_FID")
    intersect_end_time = dt.now()
    calculate_runtime(intersect_start_time, intersect_end_time, operation="PairwiseIntersect", layer="mpas_merged & subregions_ALL")

    with arcpy.da.UpdateCursor("mpas_merged", [merged_name_field, mpa_subregion_field]) as cursor_mpa:
        for mpa in cursor_mpa:
            mpa_name = (mpa[0].replace("'", "''"))   #.encode('utf8')
            where = "{0} = '{1}'".format(merged_name_field, mpa_name)
            with arcpy.da.SearchCursor("mpa_sub_intersect", [merged_name_field, "subregion", "Shape_Area"], where) as cursor_mpasub:
                shpArea = 0.0
                subr = None
                for row in cursor_mpasub:
                    if row[2] > shpArea:
                        shpArea = row[2]
                        subr = row[1]
                mpa[1] = subr
                cursor_mpa.updateRow(mpa)
    arcpy.Delete_management("mpa_sub_intersect")

    # NOTE: The field name was changed to _TOTAL so the area needs to be calculated
    # before the ecosections intersect so that the area of the total MPA is carried forward.
    calculateArea("mpas_merged", mpa_area_field)
    # NOTE: Since the marine area of the protected area is being used, the total should
    # be calculated as the marine area.
    arcpy.CalculateField_management("mpas_merged", mpa_area_field, '!' + mpa_marine_area + '!')

    # Intersect MPAs and ecosections
    intersect2_start_time = dt.now()
    arcpy.analysis.PairwiseIntersect(["mpas_merged",ecosections_layer], "mpa_ecosect_intersect")
    intersect2_end_time = dt.now()
    calculate_runtime(intersect2_start_time, intersect2_end_time, operation="PairwiseIntersect", layer="mpas_merged & mpa_ecosect_intersect")

    # Dissolve (aggregate) by MPA and ecosection
    dissolve_start_time = dt.now()
    arcpy.analysis.PairwiseDissolve("mpa_ecosect_intersect", final_mpa_fc_name, [merged_name_field, "ecosection"],
                              [[mpa_subregion_field, "FIRST"],[mpa_area_field, "FIRST"]],"MULTI_PART")
    dissolve_end_time = dt.now()
    calculate_runtime(dissolve_start_time, dissolve_end_time, operation="PairwiseDissolve", layer="mpa_ecosect_intersect")

    # Rename fields to remove the prefixes that were appended in the Dissolve operation
    renameField(final_mpa_fc_name, 'FIRST_' + mpa_subregion_field, mpa_subregion_field, 'TEXT')
    renameField(final_mpa_fc_name, 'FIRST_' + mpa_area_field, mpa_area_field, 'DOUBLE')

    # Add area field to calculate the area of each piece of an MPA in overlapping ecosections
    calculateArea(final_mpa_fc_name, mpa_area_attribute_section)

    # Clean up the merged and intersected intermediate datasets
    arcpy.Delete_management(["mpas_merged", "mpa_ecosect_intersect"])

    return final_mpa_fc_name


## loadLayer ##
#
# Loads and processes a geospatial layer.
# Returns the layer with its original name.
#
# Details: Copies a layer into the temporary workspace, reprojects it,
# calculates area fields, and removes unnecesary fields. If layer is
# complex, the layer is split to single-part features before other
# calculations are performed. This layer-splitting will often help
# processes succeed that would fail otherwise.
#
def loadLayer(source_aprx, layer_name, sr_code, new_bc_area_field,
              new_bc_total_area_field, is_complex, density_field, value_type):

    logger_file.debug('Starting function')

    if detailed_status:
        logger_multi.info('Loading ' + layer_name)

    # Find layer in APRX
    aprx = arcpy.mp.ArcGISProject(source_aprx).listMaps(source_mapframe_name)[0]
    layer = aprx.listLayers(layer_name)[0]

    # Load layer into workspace and reproject
    working_layer = layer.name
    orig_name = working_layer
    arcpy.env.XYResolution = "0.0001 Meters" # project will fail if a resolution is set too low
    arcpy.Project_management(layer.dataSource, layer.name,
                             arcpy.SpatialReference(sr_code))

    # If layer is complex, split multi-part features into single-part features
    if is_complex:
        if detailed_status:
            logger_multi.info('...Exploding complex feature class')

        arcpy.MultipartToSinglepart_management(working_layer, working_layer+'_c')

        # Clean up temporary data
        if cleanUpTempData:
            arcpy.Delete_management(working_layer)

        working_layer = working_layer+'_c'

    keep_fields = ['ecosection', density_field]

    # Delete fields that aren't important
    for field in arcpy.ListFields(working_layer):
        if field.type in ['OID','Geometry']:
            continue
        if field.required:
            continue
        if field.name not in keep_fields:
            arcpy.DeleteField_management(working_layer, field.name)

    # Add new area fields
    arcpy.AddField_management(working_layer, new_bc_area_field, "DOUBLE")
    arcpy.AddField_management(working_layer, new_bc_total_area_field, "DOUBLE")

    # Calculate feature area and total area
    calculateArea(working_layer, new_bc_area_field)

    # Calculate total based on if it is a density- or area-based feature.
    # NOTE: The new_bc_area_field needs to be an area value at this point, 
    # but the total area needs to be changed.
    if value_type == 'density':
        total_area = calculateTotalArea(working_layer, density_field)
    else:
        total_area = calculateTotalArea(working_layer, new_bc_area_field)
    arcpy.CalculateField_management(working_layer, new_bc_total_area_field, total_area)

    if working_layer != orig_name:
        if arcpy.Exists(orig_name):
            arcpy.Rename_management(orig_name, orig_name + '_original')
        arcpy.Rename_management(working_layer, orig_name)

    return orig_name


## loadRegionLayer ##
#
# Loads and processes a geospatial layer (similar to loadLayer()).
# Returns the layer with its original name.
#
def loadRegionLayer(source_aprx, layer_name, sr_code, new_bc_area_field, new_bc_total_area_field):

    logger_file.debug('Starting function')

    if detailed_status:
        logger_multi.info('Loading ' + layer_name)

    # Find layer in APRX
    aprx = arcpy.mp.ArcGISProject(source_aprx).listMaps(source_mapframe_name)[0]
    layer = aprx.listLayers(layer_name)[0]

    # Load layer into workspace and reproject
    working_layer = layer.name
    arcpy.Project_management(layer.dataSource, layer.name,
                             arcpy.SpatialReference(sr_code))

    # Add new area fields
    arcpy.AddField_management(working_layer, new_bc_area_field, "DOUBLE")
    arcpy.AddField_management(working_layer, new_bc_total_area_field, "DOUBLE")

    # Calculate feature area and total area
    calculateArea(working_layer, new_bc_area_field)
    total_area = calculateTotalArea(working_layer, new_bc_area_field)
    arcpy.CalculateField_management(working_layer, new_bc_total_area_field, total_area)

    return working_layer


## buildThresholdDict ##
#
# Reads a CSV that lists CP/HU layers and the threshold values that
# denote their presence in an MPA.
# Returns a dictionary with the layer names and their threshold values.
#
# Details: The first column of the CSV is an mpatt dataset name
# and the second is the threshold that determines whether it is present
# in an MPA. In the resulting dictionary, the key-value pairs are the
# mpatt dataset names and their threshold values.
#
def buildThresholdDict(layer_presence_threshold_file):

    logger_file.debug('Starting function')

    thresholds = {}
    with open(layer_presence_threshold_file, 'r') as csvfile:
        reader = list(csv.reader(csvfile))
        for row in reader:
            fc_name = row[0]
            layer_threshold = row[1]
            thresholds[fc_name] = layer_threshold

    return thresholds


## renameField ##
#
# Adds a new field with the desired name (ofield), copies values from an
# original field (ifield) and deletes the original field.
#
def renameField(working_layer, ifield, ofield, ftype):

    logger_file.debug('Starting function')

    arcpy.AddField_management(working_layer, ofield, ftype)
    arcpy.CalculateField_management(working_layer, ofield, '!{0}!'.format(ifield), 'PYTHON_9.3')
    arcpy.DeleteField_management(working_layer, ifield)


## readMPAInclusionMatrix ##
#
# Reads the data from the inclusion matrix CSV (permitted/restricted
# HU activities in MPAs).
# Returns a dictionary with the inclusion matrix data.
#
# Details: The first row of the CSV contains mpatt HU feature class names
# and the first column contains MPA names matching those in the MPA feature
# classes. See inclusion_matrix_path variable definition comments for more details.
#
def readMPAInclusionMatrix(mpath):

    logger_file.debug('Starting function')

    inclusion_matrix = {}
    with open(mpath, 'r') as csvfile:
        reader = list(csv.reader(csvfile))
        header = reader[0]
        for row in reader[1:]:
            # Get MPA from first column
            mpa = row[0]
            inclusion_matrix[mpa] = {}
            # Iterate through row skipping first col
            for i in range(1, len(row)):
                fc_name = header[i]
                inclusion_matrix[mpa][fc_name] = row[i].strip() if row[i].strip() in ('O', 'X', 'C','na') else None
    return inclusion_matrix


## shouldInclude ##
#
# Tests to see if a feature belongs in an MPA as guided by the inclusion matrix.
# Returns True/False.
#
def shouldInclude(pct_in_mpa, threshold, im, fc, mpa):

    # If MPA is not in inclusion matrix, use conventional inclusion test
    if mpa not in im:
        return pct_in_mpa > threshold
    # If feature class not in inclusion matrix, use conventional inclusion test
    if fc not in im[mpa] and fc not in hu_multiple:
        return pct_in_mpa > threshold

    # If feature class has a variation, then do a separate set of tests
    if fc in hu_multiple:
        ival_list = []
        for variant in hu_multiple[fc]['variants']:
            if variant in im[mpa]:
                ivaltemp = im[mpa][variant]
                ival_list.append(ivaltemp)
        if not ival_list:
            # This handles the case where there are no variations in the 
            # inclusion matrix but the user provides some in the hu_multiple
            # variable. In this case, if the ival_list is blank but the base hu 
            # is in im[mpa] then get the base value. It's also possible that a
            # user could incorrectly create an inclusion matrix where they include the 
            # base hu and variations even though only the variations should be referenced.
            if fc in im[mpa]:
                ival_list.append(im[mpa][fc])
            else:
                return pct_in_mpa > threshold
        # If HU is permitted or not restricted and override is disabled then
        # include it
        if ('O' in ival_list or 'C' in ival_list) and not override_y:
            return True
        # If HU is restricted and override is disabled then do not include it
        if ('X' in ival_list or 'na' in ival_list) and not override_n:
            return False
        # Otherwise override whatever value is in i_val with conventional test
        return pct_in_mpa > threshold

    # Get inclusion value
    i_val = im[mpa][fc]
    # If inclusion value was blank, use conventional inclusion test
    if i_val is None:
        return pct_in_mpa > threshold
    # If inclusion value is permitted or not restricted and override is disabled
    # then include it
    if i_val in ['O', 'C'] and not override_y:
        return True
    # See above but for restricted
    if i_val in ['X', 'na'] and not override_n:
        return False
    # Otherwise override whatever value is in i_val with conventional test
    return pct_in_mpa > threshold


## process_geometry ##
#
# Performs geometric operations on CP/HU layers to determine the amount
# of each layer that falls within each MPA.
# Returns the layer updated with new fields containing area measurements
# and additional calculations.
#
# Details: Determines what area of a feature falls in each MPA. Also
# performs a subregional analysis if a region_layer is provided. Returns
# a feature class with the adjusted and clipped area and the original area
# of the feature class, the enclosing MPA, percentages comparing the clipped/
# adjusted size to the MPA size, and the original size of the feature class.
#
def process_geometry(base_layer, final_mpa_fc_name, clipped_adjusted_area, mpa_name_attribute,
                    mpa_area_attribute, new_bc_total_area_field, pct_of_mpa_field, pct_of_total_field,
                    mpa_subregion_field, mpa_area_attribute_section, clipped_adj_area_mpaTotal, pct_of_mpa_field_Total,
                    density_field, value_type):

    logger_file.debug('Starting function')

    working_intersect = base_layer + '_Intersect'

    # Intersect with MPAs and explode to singlepart
    if detailed_status:
        logger_multi.info('...Intersecting ' + base_layer)
    intersect_start_time = dt.now()
    arcpy.analysis.PairwiseIntersect([base_layer, final_mpa_fc_name], working_intersect)
    intersect_end_time = dt.now()
    calculate_runtime(intersect_start_time, intersect_end_time, operation="PairwiseIntersect", layer=base_layer)

    # Add new field 'clipped_adjusted_area' (name: 'etp_ac_area_adj')
    # and populate it with the shape area values of the working layer.
    arcpy.AddField_management(working_intersect, clipped_adjusted_area, 'DOUBLE')
    arcpy.CalculateField_management(working_intersect, clipped_adjusted_area, '!shape.area!')

    # If it is a density/diversity based feature, check if cell was clipped
    # and rescale density value
    if value_type == 'density':
        with arcpy.da.UpdateCursor(working_intersect, [density_field, clipped_adjusted_area, new_bc_area_field]) as cursor:
            for row in cursor:
                if row[1] != row[2]:
                    newValue = (row[1]/row[2]) * row[0]  # newValue = (newarea/oldarea) * value
                    row[1] = newValue
                    row[2] = row[0] # Make the feature area the original density value
                else:
                    row[1] = row[0]
                    row[2] = row[0]
                cursor.updateRow(row)

    # Dissolve by mpa_name_attribute field summing adjusted area
    working_dissolved = base_layer + '_Dissolved'
    if detailed_status:
        logger_multi.info('...Dissolving ' + base_layer)
    dissolve_start_time = dt.now()
    arcpy.analysis.PairwiseDissolve(working_intersect, working_dissolved, [mpa_name_attribute, "ecosection"],
                            [[clipped_adjusted_area, 'SUM'], [new_bc_total_area_field, 'FIRST'],
                            [mpa_area_attribute, 'FIRST'], [mpa_area_attribute_section, 'FIRST'],
                            [mpa_subregion_field, 'FIRST']])
    dissolve_end_time = dt.now()
    calculate_runtime(dissolve_start_time, dissolve_end_time, operation="PairwiseDissolve", layer=working_intersect)

    # Rename fields
    renameField(working_dissolved, 'SUM_' + clipped_adjusted_area, clipped_adjusted_area, 'DOUBLE')
    renameField(working_dissolved, 'FIRST_' + new_bc_total_area_field, new_bc_total_area_field, 'DOUBLE')
    renameField(working_dissolved, 'FIRST_' + mpa_area_attribute, mpa_area_attribute, 'DOUBLE')
    renameField(working_dissolved, 'FIRST_' + mpa_area_attribute_section, mpa_area_attribute_section, 'DOUBLE')
    renameField(working_dissolved, 'FIRST_' + mpa_subregion_field, mpa_subregion_field, 'TEXT')

    # Add new fields to capture percentages
    arcpy.AddField_management(working_dissolved, pct_of_mpa_field, 'DOUBLE')
    arcpy.AddField_management(working_dissolved, clipped_adj_area_mpaTotal, 'DOUBLE')
    arcpy.AddField_management(working_dissolved, pct_of_mpa_field_Total, 'DOUBLE')
    arcpy.AddField_management(working_dissolved, pct_of_total_field, 'DOUBLE')

    # Calculate percentages
    arcpy.CalculateField_management(working_dissolved, pct_of_mpa_field,
                                    '!{0}!/!{1}!'.format(clipped_adjusted_area,mpa_area_attribute))
    arcpy.CalculateField_management(working_dissolved, pct_of_total_field,
                                    '!{0}!/!{1}!'.format(clipped_adjusted_area,new_bc_total_area_field))

    # Calculate new total fields
    # Get unique list of MPAs
    mpa_list = []
    with arcpy.da.SearchCursor(working_dissolved, [mpa_name_attribute]) as cursor:
        for row in cursor:
            if row[0] not in mpa_list:
                mpa_list.append(row[0])

    # Add up feature spatial areas by MPA (parts in ecosections)
    for mpa in mpa_list:
        mpa_name = (mpa.replace("'", "''"))  #.encode('utf8')
        where = "{0} = '{1}'".format(mpa_name_attribute, mpa_name)

        # Calculate 'clipped_adj_area_mpaTotal' value

        # NOTE: The 'clipped_adj_area_mpaTotal' calculation (in arcpy.da.UpdateCursor())
        # was changed to shape area ('SHAPE@AREA') to get the areal overlap. This was done
        # to ensure the mpaTotal fields ('clipped_adj_area_mpaTotal' and 'pct_of_mpa_field_Total')
        # were area-based. The 'pct_of_mpa_field_total' is referenced again during the sliver 
        # assessment and needs to be area-based for this analysis. The 'adj' component of the name
        # 'clipped_adj_area_mpaTotal' isn't completely applicable now but will be retained.
        with arcpy.da.UpdateCursor(working_dissolved, ['SHAPE@AREA', clipped_adj_area_mpaTotal], where) as cursor:
            sum_area = 0.0
            for row in cursor:
                sum_area += row[0]
            cursor.reset()
            for row in cursor:
                row[1] = sum_area
                cursor.updateRow(row)
    
    # Calculate 'pct_of_mpa_field_Total' value
    arcpy.CalculateField_management(working_dissolved, pct_of_mpa_field_Total,
                                    '!{0}!/!{1}!'.format(clipped_adj_area_mpaTotal, mpa_area_attribute))

    if cleanUpTempData:
        for layer in arcpy.ListFeatureClasses(base_layer + '_*'):
            if layer != working_dissolved:
                arcpy.Delete_management(layer)

    return working_dissolved


## calculate_presence ##
#
# Calculates the presence of CP/HU layers within each MPA.
# Returns a dictionary with details about the passed layer's presence in each MPA.
#
# The first key in the dict is the mpa name which points to another dict.
# This dict has the following key-value pairs:
#     'clip_area'     -> The adjusted and clipped area of the layer in the mpa
#     'orig_area'     -> The original area of the layer
#     'mpa_area'      -> The area of the MPA
#     'region_area'   -> The area of the clipped region
#     'pct_in_mpa'    -> clip_area / mpa_area
#     'pct_of_region' -> clip_area / region_area
#     'pct_of_total'  -> clip_area / orig_area
#
def calculate_presence(working_layer, final_mpa_fc_name, clipped_adjusted_area, pct_of_total_field, pct_of_mpa_field,
                       mpa_name_attribute, threshold, imatrix, mpa_subregion_field, mpa_area_attribute_section,
                       clipped_adj_area_mpaTotal, pct_of_mpa_field_Total, density_field, value_type):

    logger_file.debug('Starting function')

    mpas = {}
    sliver_freq = {} # To store the sliver frequencies

    # Return total area of the working layer as "region_area"
    region_area = calculateTotalArea(working_layer, new_bc_area_field)

    # Crunch the geometry for the whole region
    processed_layer = process_geometry(working_layer, final_mpa_fc_name, clipped_adjusted_area,
                                       mpa_name_attribute, mpa_area_attribute, new_bc_total_area_field,
                                       pct_of_mpa_field, pct_of_total_field, mpa_subregion_field,
                                       mpa_area_attribute_section, clipped_adj_area_mpaTotal, pct_of_mpa_field_Total,
                                       density_field, value_type)

    # Read the statistics for the whole region into a dict
    with arcpy.da.SearchCursor(processed_layer,
                               [mpa_name_attribute,mpa_area_attribute,pct_of_mpa_field, pct_of_total_field,
                                new_bc_total_area_field, clipped_adjusted_area, "ecosection", mpa_subregion_field,
                                mpa_area_attribute_section, clipped_adj_area_mpaTotal, pct_of_mpa_field_Total]
                                ) as cursor:
        # i.e. for each MPA which technically has HU/CP in it
        for row in cursor:
            mpa_name, mpa_area, pct_of_mpa = row[0], row[1], row[2]
            pct_of_total, hucp_og_area, hucp_clip_area = row[3], row[4], row[5]
            ecosect, subreg_mpa, mpa_area_ecosect  = row[6], row[7], row[8]
            hucp_clip_area_mpaTotal, pct_of_mpa_Total = row[9], row[10]

            # Checks if HU/CP makes up greater than 5% (or whatever) of MPA
            name = working_layer
            if mpa_name not in sliver_freq:
                sliver_freq[mpa_name] = {'pct_overlap_cphu_mpa': pct_of_mpa_Total}
                # This should only need to be written once, even if there are multiple features for each MPA

            if shouldInclude(pct_of_mpa_Total, threshold, imatrix, name, mpa_name):
                pct_of_region = (hucp_clip_area / region_area) if region_area is not None else None
                if mpa_name not in mpas:
                    mpas[mpa_name] = {}
                mpas[mpa_name][ecosect] = {'subregion': subreg_mpa,
                                  'clip_area': hucp_clip_area,
                                  'orig_area': hucp_og_area,
                                  'mpa_area': mpa_area,
                                  'region_area': region_area,
                                  'pct_in_mpa': pct_of_mpa,
                                  'pct_of_region': pct_of_region,
                                  'pct_of_total': pct_of_total}

    if cleanUpTempData:
        arcpy.Delete_management(working_layer)
        arcpy.Delete_management(processed_layer)

    return mpas, sliver_freq


## buildOverlapDict ##
#
# Uses the CP area overlap CSV to populate a dictionary.
# Returns the dictionary with the existing overlap data.
#
# This function is only called if cpOverlap_newDict = False. In other
# words, this function will use existing CSV overlap data rather than
# recalculating all CP area overlaps from scratch.
#
def buildOverlapDict(cpOverlap_DictPath, cp_area_overlap_dict):

    logger_file.debug('Starting function')

    with open(cpOverlap_DictPath, 'r') as csvfile:
        reader = list(csv.reader(csvfile))
        for row in reader[1:]:
            fc_name = row[0]
            section = row[1]
            area = float(row[2])
            if fc_name not in cp_area_overlap_dict:
                cp_area_overlap_dict[fc_name] = {}
            if section not in cp_area_overlap_dict[fc_name]:
                cp_area_overlap_dict[fc_name][section] = {}
            cp_area_overlap_dict[fc_name][section] = {'Area': area}
    return cp_area_overlap_dict


## calcCPlyrOverlap ##
#
# Intersects CP layers with subregions/ecosections to obtain the total
# area/value of a CP within each subregion/ecosection (total overlap).
# Returns a dictionary with the CP overlap data.
#
# This function will be called if the script is configured to calculate
# all CP overlaps from scratch (cpOverlap_newDict = True) or if some CP
# features do not exist in the dictionary built from the existing overlap CSV.
#
def calcCPlyrOverlap(cp_area_overlap_dict, working_layer, ecosections_layer, subregions_ALL, density_field, value_type):

    logger_file.debug('Starting function')

    # intersect
    subr_union = working_layer + '_subUnion'
    ecos_union = working_layer + '_ecoUnion'

    # Union with subregions-ecosections (overlapping parts should not
    # be combined)

    if detailed_status:
        logger_multi.info('...Union ' + working_layer)
    
    # Union with subregions
    union_start_time = dt.now()
    arcpy.Union_analysis([working_layer, subregions_ALL], subr_union)
    union_end_time = dt.now()
    calculate_runtime(union_start_time, union_end_time, operation="Union_analysis (subregions)", layer=working_layer)

    # Union with ecosections
    union2_start_time = dt.now()
    arcpy.Union_analysis([working_layer, ecosections_layer], ecos_union)
    union2_end_time = dt.now()
    calculate_runtime(union2_start_time, union2_end_time, operation="Union_analysis (ecosections)", layer=working_layer)

    # Delete records that do not overlap
    FID_wlyr = "FID_" + working_layer
    if len(FID_wlyr) > 64:
        cut = len(FID_wlyr) - 64
        FID_wlyr = FID_wlyr[:-cut]
    FID_subr = "FID_" + subregions_ALL
    FID_ecos = "FID_" + ecosections_layer
    with arcpy.da.UpdateCursor(subr_union, [FID_wlyr, FID_subr]) as cursor:
        for row in cursor:
            if row[0] == -1 or row[1] == -1:
                cursor.deleteRow()
    with arcpy.da.UpdateCursor(ecos_union, [FID_wlyr, FID_ecos]) as cursor:
        for row in cursor:
            if row[0] == -1 or row[1] == -1:
                cursor.deleteRow()

    # Add area field that will be summed when dissolving
    ecosub_area_field = 'ecosub_area'
    arcpy.AddField_management(subr_union, ecosub_area_field, "DOUBLE")
    arcpy.AddField_management(ecos_union, ecosub_area_field, "DOUBLE")
    arcpy.CalculateField_management(subr_union, ecosub_area_field, '!shape.area!')
    arcpy.CalculateField_management(ecos_union, ecosub_area_field, '!shape.area!')

    # If it is a density/diversity-based feature, recalculate area field in case it was clipped
    if value_type == 'density':
        with arcpy.da.UpdateCursor(subr_union, [density_field, ecosub_area_field, new_bc_area_field]) as cursor:
            for row in cursor:
                if row[1] != row[2]:
                    newValue = (row[1]/row[2]) * row[0]  # newValue = (newarea/oldarea) * value
                    row[1] = newValue
                else:
                    row[1] = row[0]
                cursor.updateRow(row)
    if value_type == 'density':
        with arcpy.da.UpdateCursor(ecos_union, [density_field, ecosub_area_field, new_bc_area_field]) as cursor:
            for row in cursor:
                if row[1] != row[2]:
                    newValue = (row[1]/row[2]) * row[0]
                    row[1] = newValue
                else:
                    row[1] = row[0]
                cursor.updateRow(row)

    # Dissolve by ecosection/subregion field summing ecosub_area_field

    subr_dissolved = working_layer + '_subDissolved'
    ecos_dissolved = working_layer + '_ecoDissolved'
    if detailed_status:
        logger_multi.info('...Dissolving ' + working_layer)

    # Dissolve by subregion field
    dissolve_start_time = dt.now()
    arcpy.analysis.PairwiseDissolve(subr_union, subr_dissolved, ['subregion'], [[ecosub_area_field, 'SUM']])
    dissolve_end_time = dt.now()
    calculate_runtime(dissolve_start_time, dissolve_end_time, operation="PairwiseDissolve (subregions)", layer=subr_union)

    # Dissolve by ecosection field
    dissolve2_start_time = dt.now()
    arcpy.analysis.PairwiseDissolve(ecos_union, ecos_dissolved, ['ecosection'], [[ecosub_area_field, 'SUM']])
    dissolve2_end_time = dt.now()
    calculate_runtime(dissolve2_start_time, dissolve2_end_time, operation="PairwiseDissolve (ecosections)", layer=ecos_union)

    cp_area_overlap_dict[working_layer] = {}
    with arcpy.da.SearchCursor(subr_dissolved, ['subregion', "SUM_" + ecosub_area_field]) as cursor:
        for row in cursor:
            cp_area_overlap_dict[working_layer][row[0]] = {'Area' : row[1]}
    with arcpy.da.SearchCursor(ecos_dissolved, ['ecosection', "SUM_" + ecosub_area_field]) as cursor:
        for row in cursor:
            cp_area_overlap_dict[working_layer][row[0]] = {'Area' : row[1]}

    if cleanUpTempData:
        arcpy.Delete_management(subr_union)
        arcpy.Delete_management(ecos_union)
        arcpy.Delete_management(subr_dissolved)
        arcpy.Delete_management(ecos_dissolved)

    return cp_area_overlap_dict


## calcEffectivenessScore ##
#
# Analyzes the number of interactions for a CP broken down by severity
# (count of HIGH and MODERATE interactions).
# Returns an effectiveness score. If the HIGH/MODERATE interaction counts
# are 0, the effectiveness score is negligible (1.0).
#
def calcEffectivenessScore(num_high, num_mod):
    if num_high > 0 or num_mod > 4: # High
        return 0.0
    elif num_mod == 4: # Moderate-High
        return 0.24
    elif num_mod == 3: # Moderate
        return 0.6
    elif num_mod > 0 and num_mod < 3: # Low impact
        return 0.85
    else: # Negligible
        return 1.0


## countInteractions ##
#
# Counts the interactions by severity (HIGH and MODERATE) for easy
# reading into calcEffectivenessScore() function.
# Returns counts for HIGH and MODERATE interactions which will be used
# to calculate the effectiveness scores. 
#
def countInteractions(i_list):
    num_high = 0
    num_mod = 0
    for interaction in i_list:
        if interaction == 'HIGH':
            num_high = num_high + 1
        elif interaction == 'MODERATE':
            num_mod = num_mod + 1
    return (num_high, num_mod)


## loadInteractionsMatrix ##
#
# Reads the data from the interactions matrix CSV and standardizes
# the interaction severity (HIGH, MODERATE, NEGLIGIBLE).
# Returns a dictionary with the interactions matrix data.
#
# Details: In the resulting dict, the first key is the CP dataset name and
# the second key is the HU dataset name. The value is the interaction severity.
#
def loadInteractionsMatrix(imatrix_path):

    logger_file.debug('Starting function')

    imatrix = {}
    with open(imatrix_path, 'r') as csvfile:
        reader = list(csv.reader(csvfile))
        regex = re.compile('[^a-zA-Z]')
        for row in reader[1:]:
            cp = '_'.join(row[1].split('_')[2:4])  # Reference the 3rd and 4th parts of the UID
            hu = regex.sub('', row[3]).lower()
            interaction = row[5]

            if interaction == 'VERY HIGH' or interaction == 'Major Negative':
                interaction = 'HIGH'
            if interaction == 'MEDIUM' or interaction == 'Minor Negative':
                interaction = 'MODERATE'
            if interaction == 'Negligible' or interaction == 'NEGLIGIBLE':
                interaction = 'NEGLIGIBLE'

            if cp not in imatrix:
                imatrix[cp] = {}
            imatrix[cp][hu] = interaction
    return imatrix


## determineInteraction ##
#
# Gets the relevent part of the CP/HU dataset names.
# Returns the interaction value from the interaction matrix.
#
def determineInteraction(imatrix, cp, hu, mpa):
    cp = '_'.join(cp.split('_')[2:4])
    length = len(cp)
    # Truncate ri1, etc off colonies UIDs so that they match the imatrix
    if cp[length-3:-1] == 'ri':
        cp = cp[:-3]
        length = 0

    if cp in imatrix:
        if hu in hu_multiple:
            hu_orig = hu
            scores = []
            hu_list = []
            for variant in hu_multiple[hu_orig]['variants']:
                hu = variant.split('_')
                hu = (''.join(hu[3] + hu[-1])).lower()
                if hu in imatrix[cp]:
                    # At this point the hu_orig has passed through the shouldInclude function and 
                    # considered the overrides, and at least one variant is considered present.
                    # Now the script considers the scenario where the inclusion matrix denotes that 
                    # an HU activity is not present (in this scenario, either the script does not 
                    # use spatial data, or override_n is False and spatial overlap isn't considered).
                    exclude = override_n is False and (inclusion_matrix[mpa][variant] == 'X' or inclusion_matrix[mpa][variant] == 'na')
                    if not exclude:
                        scores.append(imatrix[cp][hu])
                        hu_list.append(variant)
            hu_orig = hu_orig.split('_')[3]
            if 'HIGH' in scores:
                return 'HIGH', scores, hu_list
            elif 'MODERATE' in scores:
                return 'MODERATE', scores, hu_list
            elif 'NEGLIGIBLE' in scores:
                return 'NEGLIGIBLE', scores, hu_list
            elif hu_orig in imatrix[cp]:
                # if it gets to this point, then scores list is empty, which 
                # means none of the variants are in the interaction matrix
                return imatrix[cp][hu_orig], [], []
            else:
                return None, scores, hu_list
        else:
            hu = hu.split('_')[3]
            if hu in imatrix[cp]:
                return imatrix[cp][hu], [], []
    return None, [], []


## identifyInteractions ##
#
# Finds HUs and CPs in the same MPA and checks if they have an interaction.
# Returns a dictionary with interaction scaling factors for each CP in each MPA.
#
def identifyInteractions(hu_in_mpas, cp_in_mpas, imatrix):

    logger_file.debug('Starting function')

    cp_in_mpa_i = {}

    for mpa in hu_in_mpas:
        if mpa not in cp_in_mpas:
            continue
        if mpa not in cp_in_mpa_i:
            cp_in_mpa_i[mpa] = {}
        for ecosection in cp_in_mpas[mpa]:
            # The analysis only needs to know the interaction once.
            # The ecosection doesn't matter here.
            for cp in cp_in_mpas[mpa][ecosection]:
                if cp not in cp_in_mpa_i[mpa]:
                        cp_in_mpa_i[mpa][cp] = {'interactions': [],
                                                'eff_score': None}
                else:
                    continue  # The CP is only needed once per MPA; if already encountered, skip it.
                for hu in hu_in_mpas[mpa]:
                    interaction, score_list, hu_list = determineInteraction(imatrix, cp, hu, mpa)
                    if interaction is not None:
                        cp_in_mpa_i[mpa][cp]['interactions'].append(interaction)

    # Add in any MPAs that were not in hu_in_mpas but were in cp_in_mpas. These
    # need to be carried forward, even if they do not have any interactions.
    for mpa in cp_in_mpas:
        if mpa not in cp_in_mpa_i:
            cp_in_mpa_i[mpa] = {}
            for ecosection in cp_in_mpas[mpa]:
                for cp in cp_in_mpas[mpa][ecosection]:
                    if cp not in cp_in_mpa_i[mpa]:
                        cp_in_mpa_i[mpa][cp] = {'interactions': [],
                                                'eff_score': None}
                else:
                    continue  # The CP is only needed once per MPA; if already encountered, skip it.

    return cp_in_mpa_i


## prepareOutputTable1 ##
#
# Consolidates all data in a dictionary that can be used to create the
# final output table. Calculates effectiveness scores and uses them to scale the CPs.
# Returns a dictionary with all relevant scaled and unscaled data.
#
# The returned dict is structured like so: o_table_1[ MPA NAME ][ REGION ][ CP ]
# This points to a dict that has the following keys:
# 'mpa_area'     -> area of the enclosing mpa
# 'og_area'      -> total area of the original CP
# 'uscaled_area' -> area of the clipped and adjusted CP in the MPA
# 'scaled_area'  -> uscaled_area but multiplied by the CPs effectiveness score
# 'pct_of_mpa'   -> scaled_area / mpa_area
# 'pct_of_og'    -> scaled_area / og_area
#
def prepareOutputTable1(cp_in_mpa_i, cp_in_mpas):

    logger_file.debug('Starting function')

    o_table_1 = {}

    ecosections = ["Johnstone Strait", "Continental Slope", "Dixon Entrance", "Strait of Georgia",
                   "Juan de Fuca Strait", "Queen Charlotte Strait", "North Coast Fjords", "Hecate Strait",
                   "Queen Charlotte Sound", "Vancouver Island Shelf", "Transitional Pacific", "Subarctic Pacific"]

    for mpa in cp_in_mpa_i:
        if mpa not in o_table_1:
            o_table_1[mpa] = {}

        for cp in cp_in_mpa_i[mpa]:
            for ecosection in ecosections:
                if ecosection in cp_in_mpas[mpa] and cp in cp_in_mpas[mpa][ecosection]:
                    if ecosection not in o_table_1[mpa]:
                        o_table_1[mpa][ecosection] = {}

                    # Pre-populate dict with already known values
                    if cp not in o_table_1[mpa][ecosection]:
                        o_table_1[mpa][ecosection][cp] = {'mpa_area': cp_in_mpas[mpa][ecosection][cp]['mpa_area'],
                                                      'og_area': cp_in_mpas[mpa][ecosection][cp]['orig_area'],
                                                      'unscaled_area': cp_in_mpas[mpa][ecosection][cp]['clip_area'],
                                                      'scaled_area': None,
                                                      'pct_of_mpa': None,
                                                      'pct_of_og': None,
                                                      'pct_of_og_unscaled': None,
                                                      'subregion': cp_in_mpas[mpa][ecosection][cp]['subregion']}

                    # Calculate effectiveness
                    num_high, num_mod = countInteractions(cp_in_mpa_i[mpa][cp]['interactions'])
                    cp_in_mpa_i[mpa][cp]['eff_score'] = calcEffectivenessScore(num_high, num_mod)

                    # Rescale areas and calculate new percentages
                    eff_score = cp_in_mpa_i[mpa][cp]['eff_score']
                    unscaled_area = o_table_1[mpa][ecosection][cp]['unscaled_area']
                    o_table_1[mpa][ecosection][cp]['scaled_area'] = eff_score * unscaled_area

                    scaled_area = o_table_1[mpa][ecosection][cp]['scaled_area']
                    mpa_area = o_table_1[mpa][ecosection][cp]['mpa_area']
                    og_area = o_table_1[mpa][ecosection][cp]['og_area']

                    o_table_1[mpa][ecosection][cp]['pct_of_mpa'] = scaled_area / mpa_area
                    o_table_1[mpa][ecosection][cp]['pct_of_og'] = scaled_area / og_area
                    o_table_1[mpa][ecosection][cp]['pct_of_og_unscaled'] = unscaled_area / og_area

    return o_table_1


## writeOutputTable1 ##
#
# Writes the Table 1 dictionary to a CSV file.
#
def writeOutputTable1(otable, opath, mpa_dict):

    logger_file.debug('Starting function')

    with open(opath, 'w') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['UID', 'name', 'subregion', 'ecosection', 'CP', 'proportion_scaled', 'proportion_unscaled',
                    'value_scaled','value_unscaled', 'total_value'])
        for mpa in otable:
            name = mpa_dict[mpa]['name']
            for ecosection in otable[mpa]:
                for cp in otable[mpa][ecosection]:
                    pct_of_og = otable[mpa][ecosection][cp]['pct_of_og']
                    subregion = otable[mpa][ecosection][cp]['subregion']
                    unscaled_area = otable[mpa][ecosection][cp]['unscaled_area']
                    scaled_area = otable[mpa][ecosection][cp]['scaled_area']
                    total_area = otable[mpa][ecosection][cp]['og_area']
                    pct_of_og_unscaled = otable[mpa][ecosection][cp]['pct_of_og_unscaled']
                    w.writerow([mpa, name, subregion, ecosection, cp, pct_of_og, pct_of_og_unscaled, scaled_area,
                                unscaled_area, total_area])


## joinUIDtoTable1 ##
#
# Joins CP UIDs (eco UIDs from the "mpatt_eco_UID-simple" CSV file)
# to the table 1 data.
#
def joinUIDtoTable1(output1_path, ecoUIDs_path, output1join_path):

    logger_file.debug('Starting function')

    a = pd.read_csv(output1_path, encoding = "ISO-8859-1")
    b = pd.read_csv(ecoUIDs_path, encoding = "ISO-8859-1")
    joined = a.merge(b, left_on = 'CP', right_on = 'Desktop_UID', how = 'left')
    joined.to_csv(output1join_path, index = False)


## createOutputTable2 ##
#
# Retrieves CP, ecosection, and subregion data from Table 1. Determines
# original and protected areas.
# Returns this data in a dictionary.
#
def createOutputTable2(o_table_1, cp_area_overlap_dict):

    logger_file.debug('Starting function')

    table2 = {}
    fields = ['original', 'protected', 'pct']
    for mpa in o_table_1:
        for ecosection in o_table_1[mpa]:
            for cp in o_table_1[mpa][ecosection]:
                cp_data = o_table_1[mpa][ecosection][cp]
                if cp not in table2:
                    table2[cp] = {}
                if ecosection not in table2[cp]:
                    table2[cp][ecosection] = {}
                subregion = cp_data['subregion']

                # NOTE: Subregion exceptions
                # There are a few rare cases that can cause data discrepancies. This can arise when:
                # - The MPA is assigned to a subregion because some of it overlaps that subregion but 
                #   a portion of it also overlaps a blank area or a different subregion, AND
                # - A CP touches the MPA, but the CP does not touch the subregion associated with the MPA.
                # In these situations, there is a discrepancy where the subregion is not in the 
                # cp_area_overlap_dict for that CP, but it is in the o_table_1 (since this table
                # is based on the MPA).
                #
                # These situations require certain considerations:
                # - If the CP is not in the subregion, it's correct that no subregion value should be 
                #   assigned. An if statement is used to not write the subregion for this CP. 
                # - However, this means that any MPA that has a subregion of 'None' will not be carried forward.
                # - At this time, this doesn't matter because no 'None' values are written to Table 2.
                # - If in future the analysis needs to show areas that don't fall within a subregion,
                #   then some adjustments will need to be made to the code.
                #
                # There could also be cases where an MPA overlaps two subregions and is only assigned one,
                # and the CP overlaps the unlisted subregion. This won't pose problems at this time because
                # this situation only affects the middle portion of the Hecate Strait sponge reef MPA,
                # which can be split out if needed. 
                # The following if statement can help identify these areas:
                # if subregion not in cp_area_overlap_dict[cp] and subregion is not None:
                #   print cp
                #   print cp_data
                #   print mpa
                #   print cp_area_overlap_dict[cp]

                if subregion in cp_area_overlap_dict[cp]:
                    if subregion not in table2[cp]:
                        table2[cp][subregion] = {}
                for field in fields:
                    if field not in table2[cp][ecosection]:
                        table2[cp][ecosection][field] = 0.0
                if subregion in cp_area_overlap_dict[cp]:
                    for field in fields:
                        if field not in table2[cp][subregion]:
                            table2[cp][subregion][field] = 0.0
                # Get total area in ecosection
                orig_area_eco = cp_area_overlap_dict[cp][ecosection]['Area']
                if subregion in cp_area_overlap_dict[cp]:
                    if subregion is not None:
                        orig_area_sub = cp_area_overlap_dict[cp][subregion]['Area']
                    else:
                        # NOTE: Unnecessary functionality
                        # The script should never be directed to the else condition now that the 
                        # if statement above is present (if the subregion is in cp_area_overlap_dict[cp],
                        # it should never be 'None'). However, this will be left to provide context on past 
                        # functionality (previous note mentioned leaving in case the code is reverted).
                        orig_area_sub = 1 # This shouldn't matter since the pct of subregion-None won't be written to Table 2.

                # Sum up protected area from all MPAs for CP
                table2[cp][ecosection]['original'] = orig_area_eco
                table2[cp][ecosection]['protected'] = table2[cp][ecosection]['protected'] \
                                                 + cp_data['scaled_area']
                if subregion in cp_area_overlap_dict[cp]:
                    table2[cp][subregion]['original'] = orig_area_sub
                    table2[cp][subregion]['protected'] = table2[cp][subregion]['protected'] \
                                                     + cp_data['scaled_area']
    # Calculate percentages
    for cp in table2:
        for ecosub in table2[cp]:
            if table2[cp][ecosub]['original'] != 0:
                table2[cp][ecosub]['pct'] = table2[cp][ecosub]['protected']/table2[cp][ecosub]['original']

    return table2


## writeOutputTable2 ##
#
# Writes the Table 2 dictionary to a CSV file.
#
def writeOutputTable2(o_table_2, ofile):

    logger_file.debug('Starting function')

    with open(ofile, 'w') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['cp', 'ecosection_subregion', 'proportion', 'original_area', 'protected_area'])
        for cp in o_table_2:
            for eco_sub in o_table_2[cp]:
                if eco_sub is not None:
                    pct_of_ecosub = o_table_2[cp][eco_sub]['pct']
                    orig_area = o_table_2[cp][eco_sub]['original']
                    protected = o_table_2[cp][eco_sub]['protected']
                    w.writerow([cp, eco_sub, pct_of_ecosub, orig_area, protected])


## writeOutputTable3 ##
#
# Writes the percent overlap (sliver) data to a CSV file (Table 3).
#
def writeOutputTable3(percent_overlap, output3_path):

    logger_file.debug('Starting function')

    cols = ['mpa','type','cp_hu','percent_area_overlap']
    with open(output3_path, 'w') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(cols)
        for mpa in percent_overlap:
            for layer_type in percent_overlap[mpa]:
                for cphu in percent_overlap[mpa][layer_type]:
                        pct_o = percent_overlap[mpa][layer_type][cphu]['pct_overlap_cphu_mpa']
                        w.writerow([mpa, layer_type, cphu, pct_o])


## createOutputTable4 ##
#
# Creates the Table 4 data (list of CPs and HUs that interact) and writes
# data to a CSV file.
#
def createOutputTable4(hu_in_mpas, cp_in_mpas, imatrix, output4_path):

    logger_file.debug('Starting function')

    cphu_int = {}
    for mpa in hu_in_mpas:
        if mpa not in cp_in_mpas:
            continue
        if mpa not in cphu_int:
            cphu_int[mpa] = {}
        for ecosection in cp_in_mpas[mpa]:
            # we only need to know the interaction once. The ecosection doesn't matter here.
            for cp in cp_in_mpas[mpa][ecosection]:
                for hu in hu_in_mpas[mpa]:
                    interaction, score_list, hu_list = determineInteraction(imatrix, cp, hu, mpa)
                    if interaction is not None:
                        if cp not in cphu_int[mpa]:
                            cphu_int[mpa][cp] = {}
                        if len(score_list) == 0:
                            cphu_int[mpa][cp][hu] = {}
                            cphu_int[mpa][cp][hu]['interaction'] = interaction
                            if interaction != 'NEGLIGIBLE':
                                cphu_int[mpa][cp][hu]['contribute'] = 'yes'
                            else:
                                cphu_int[mpa][cp][hu]['contribute'] = 'no'
                        else:
                            contrib_decided = False
                            for i in range(len(score_list)):
                                cphu_int[mpa][cp][hu_list[i]] = {}
                                cphu_int[mpa][cp][hu_list[i]]['interaction'] = score_list[i]
                                if score_list[i] == 'HIGH' and not contrib_decided:
                                    cphu_int[mpa][cp][hu_list[i]]['contribute'] = 'yes'
                                    contrib_decided = True
                                elif score_list[i] == 'MODERATE' and 'HIGH' not in score_list and not contrib_decided:
                                    cphu_int[mpa][cp][hu_list[i]]['contribute'] = 'yes'
                                    contrib_decided = True
                                else:
                                    cphu_int[mpa][cp][hu_list[i]]['contribute'] = 'no'

    cols = ['mpa','cp','hu','score','contribute']
    with open(output4_path, 'w') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(cols)
        for mpa in cphu_int:
            for cp in cphu_int[mpa]:
                for hu in cphu_int[mpa][cp]:
                        score = cphu_int[mpa][cp][hu]['interaction']
                        contrib = cphu_int[mpa][cp][hu]['contribute']
                        w.writerow([mpa, cp, hu, score, contrib])




#######################################################################
### PROGRAM START ###
#######################################################################

logger_multi.info("Creating temporary geodatabase & setting up workspace")

#####
# Create a temporary geodatabase.
# Generate unique name for the gdb and set it as the workspace.
#####
i = 0;
while arcpy.Exists(os.path.join(working_gdb_folder, 'temp{0}.gdb'.format(str(i)))):
    i = i + 1
working_gdb = os.path.join(working_gdb_folder, 'temp{0}.gdb'.format(str(i)))
arcpy.CreateFileGDB_management(os.path.dirname(working_gdb), os.path.basename(working_gdb))
arcpy.env.workspace = working_gdb


logger_multi.info("Loading data into workspace")

#####
# Load ecosection layer into workspace and prepare data for processing.
#####
if print_status:
    logger_multi.info("Preparing Ecosections")

new_bc_area_field = 'etp_bc_area'
new_bc_total_area_field = 'etp_bc_total_area'
layer_list = arcpy.mp.ArcGISProject(source_aprx).listMaps(source_mapframe_name)[0].listLayers()
for lyr in layer_list:
    if lyr.isFeatureLayer and (lyr.name == 'eco_coarse_ecosections_polygons_d'):
        ecosections = lyr
ecosections_layer = loadLayer(source_aprx, ecosections.name, sr_code,
                              new_bc_area_field, new_bc_total_area_field,
                              None, "value", "area")


#####
# Load subregional layer into workspace and prepare data for processing.
# This layer is used to determine which subregion each MPA is in.
#####
layer_list = arcpy.mp.ArcGISProject(source_aprx).listMaps(source_mapframe_name)[0].listLayers()
for lyr in layer_list:
   if lyr.isFeatureLayer and (lyr.name.startswith('MaPP_AreaEstuaryCorrected_SR')):
       subregions_ALL = loadRegionLayer(source_aprx, lyr.name,
                                                sr_code, new_bc_area_field,
                                                new_bc_total_area_field)


#####
# Load MPA layer(s) into workspace and prepare data for processing.
#####
if print_status:
    logger_multi.info("Preparing MPAs")

mpa_area_attribute = 'etp_mpa_area_TOTAL'
merged_name_field = 'NAME_UID'  # Make sure this is unique and does not exist in any of the input
                                # MPA datasets. If it is not unique it will cause problems with the 
                                # field mapping. It may not throw an error and is hard to detect.
final_mpa_fc_name = 'mpas'
mpa_subregion_field = 'subregion_mpa'
mpa_area_attribute_section = 'etp_mpa_area_SECTION'
mpa_marine_area = 'marine_m2'   # This is now required: The terrestrial and marine portions of a 
                                # protected area have been combined, but the analysis is only 
                                # concerned with the calculation of the marine area.

# create the mpa dictionary lookup
mpa_dict = createMPAdict(source_aprx, mpa_name_field, mpa_name_e)

final_mpa_fc_name = prepareMPAs(source_aprx, sr_code, mpa_area_attribute, mpa_area_attribute_section, final_mpa_fc_name,
                                merged_name_field, mpa_name_field, mpa_subregion_field, subregions_ALL,
                                ecosections_layer, mpa_marine_area)


#####
# Load non-spatial data where applicable and store in dictionaries.
#
# This section initializes a number of dictionaries and may populate
# them with data from supplementary files (e.g., CP overlap CSV,
# layer presence threshold CSV), depending on the script configuration.
#
# CP overlap: If cpOverlap_newDict = False, the CP area overlap dict
# will be populated with CSV data. If True, the CP area overlap dict
# will be built from scratch later in the script (calcCPlyrOverlap()).
#####

# Load CP area overlap dictionary
cp_area_overlap_dict = {}
if cpOverlap_newDict is False:
    cp_area_overlap_dict = buildOverlapDict(cpOverlap_DictPath, cp_area_overlap_dict)

# Load threshold dictionary
threshold_dict = None
if layer_presence_threshold_file is not None:
    threshold_dict = buildThresholdDict(layer_presence_threshold_file)

# Load inclusion matrix
inclusion_matrix = readMPAInclusionMatrix(inclusion_matrix_path)


#####
# Load CP/HU layers into workspace (read from APRX into layer list).
#####

# Generate layer list based on dataset names
layer_list = arcpy.mp.ArcGISProject(source_aprx).listMaps(source_mapframe_name)[0].listLayers()
layer_list = [lyr for lyr in layer_list if lyr.isFeatureLayer \
              and (lyr.name.startswith('eco_') \
                   or lyr.name.startswith('hu_'))]


# Fields used in processing
clipped_adjusted_area = 'etp_ac_area_adj'
pct_of_total_field = 'pct_of_total'
pct_of_mpa_field = 'pct_of_mpa'
clipped_adj_area_mpaTotal = 'etp_ac_area_adj_mpaTotal'
pct_of_mpa_field_Total = 'pct_of_mpa_Total'
density_field = "value" # density features need to have a field named "value"


logger_multi.info("Processing layers")


#####
# Process CP/HU layers for presence in MPAs. (Begin CGA analysis.)
#
# This section begins the main CGA analysis. It will:
# - Check for edge cases (complex layers, layers based on density/diversity).
# - Load/prepare CP/HU layers for processing.
# - Determine presence threshold values.
# - Ensure all CP layers are represented in the CP overlap dict (represents
#   area/value of CP layers in each ecosection/subregion).
# - Calculate presence of CP/HU layers in MPAs.
# - Populate dictionaries with CP/HU layer data (CP/HU presence in MPAs; percent overlap)
#####

arcpy.env.overwriteOutput = True
hu_in_mpas,cp_in_mpas = {}, {}
percent_overlap = {}
for lyr in layer_list:
    if print_status:
        logger_multi.info("Processing " + lyr.name + " for presence in MPAs")

    # If a layer is complex, add it to the complexFeatureClasses list.
    # This allows complex layers to be handled differently to mitigate
    # processing failures.
    is_complex = False
    for fc in complexFeatureClasses:
        if lyr.name.startswith(fc):
            is_complex = True
            break

    # If a layer is based on density/diversity, tag layer with
    # value_type = 'density'. This allows the script to handle
    # calculations differently for these layer types.
    value_type = 'area'
    for field in arcpy.ListFields(lyr.dataSource):
        if field.name == density_field:
            value_type = 'density'
            break

    # Load and prepare the working layer (CP/HU).
    # This includes reprojecting layer to Albers, calculating areas,
    # and removing fields.
    working_layer = loadLayer(source_aprx, lyr.name, sr_code,
                              new_bc_area_field, new_bc_total_area_field,
                              is_complex, density_field, value_type)

    layer_type = 'cp' if working_layer.startswith('eco_') else 'hu'

    # Set threshold to default HU/CP presence threshold and overwrite with value in
    # threshold_dict if possible.
    threshold = hu_presence_threshold if layer_type == 'hu' else cp_presence_threshold
    if threshold_dict is not None and working_layer in threshold_dict:
        threshold = threshold_dict[working_layer]

    # If working layer is a CP layer, ensure it is present in the CP area overlap dict.
    # If layer is missing, find area or value of CP in each ecosection and subregion.
    if layer_type == 'cp' and working_layer not in cp_area_overlap_dict:
        cp_area_overlap_dict = calcCPlyrOverlap(cp_area_overlap_dict, working_layer,
                         ecosections_layer, subregions_ALL, density_field, value_type)

    # Determine if working layer is present in any MPAs and calculate statistics.
    mpa_presence, sliver_freq = calculate_presence(working_layer, final_mpa_fc_name, clipped_adjusted_area,
                                      pct_of_total_field, pct_of_mpa_field, merged_name_field, threshold,
                                      inclusion_matrix, mpa_subregion_field, mpa_area_attribute_section,
                                      clipped_adj_area_mpaTotal, pct_of_mpa_field_Total, density_field, value_type)

    # Populate HU presence dictionary (hu_in_mpas).
    # Script simply calculates the existence of HU in an MPA, not its
    # specific area. Areal measurements for HU features are not required.
    if layer_type == 'hu':
        for mpa in mpa_presence:
            if mpa not in hu_in_mpas:
                hu_in_mpas[mpa] = {}
            hu_in_mpas[mpa][working_layer] = mpa_presence[mpa]

    # Populate CP presence dictionary (cp_in_mpas).
    else:
        for mpa in mpa_presence:
            if mpa not in cp_in_mpas:
                cp_in_mpas[mpa] = {}
            for ecosection in mpa_presence[mpa]:
                if ecosection not in cp_in_mpas[mpa]:
                    cp_in_mpas[mpa][ecosection] = {}
                cp_in_mpas[mpa][ecosection][working_layer] = mpa_presence[mpa][ecosection]

    # Populate percent_overlap dictionary (sliver threshold).
    for mpa in sliver_freq:
        if mpa not in percent_overlap:
            percent_overlap[mpa] = {}
        if layer_type not in percent_overlap[mpa]:
            percent_overlap[mpa][layer_type] = {}
        percent_overlap[mpa][layer_type][working_layer] = sliver_freq[mpa]


#####
# Update CP overlap CSV with current CP area overlap data.
#
# This keeps the CSV file up-to-date with data from the
# cp_area_overlap_dict so future script runs will use the latest data.
#####

cols = ['cp','section_region','area_overlap']
with open(cpOverlap_DictPath, 'w') as f:
    w = csv.writer(f, lineterminator='\n')
    w.writerow(cols)
    for cp in cp_area_overlap_dict:
        for sec_reg in cp_area_overlap_dict[cp]:
                area_o = cp_area_overlap_dict[cp][sec_reg]['Area']
                w.writerow([cp, sec_reg, area_o])


#####
# Add HU data (from inclusion matrix) to HU presence dictionary (hu_in_mpas).
#
# This adds dummy data for HUs that should be in each MPA according to
# the inclusion matrix but didn't have spatial data that sufficiently intersected.
#
# NOTE: Unnecessary functionality
# Some values (such as areas and ecosection names) are likely not needed because
# the analysis only needs to know whether an HU exists in an MPA or not.
#####

if not override_y:
    for mpa in inclusion_matrix:
        for hu in inclusion_matrix[mpa]:
            if inclusion_matrix[mpa][hu] in ['O', 'C']:
                if mpa not in hu_in_mpas:
                    hu_in_mpas[mpa] = {}

                for fc in hu_multiple:
                    if hu in hu_multiple[fc]['variants']:
                        hu = fc
                        break

                if hu not in hu_in_mpas[mpa]:
                    hu_in_mpas[mpa][hu] = {'ecosect_placeholder':
                                           {'clip_area': 1,
                                           'orig_area': 1,
                                           'mpa_area': 1,
                                           'region_area': 1,
                                           'pct_in_mpa': 1,
                                           'pct_of_region': 1,
                                           'pct_of_total': 1}}


#####
# Clean up temporary geodatabase.
#####

if cleanUpTempData:
    logger_multi.info("Cleaning up temporary geodatabase")
    arcpy.Delete_management(working_gdb)


#####
# Find HU-CP interactions within MPAs.
#
# Loads the interactions matrix data from the CSV and standardizes the
# interaction severity. Identifies HU/CP interactions by comparing the
# HU and CP presence dictionaries to the interactions matrix.
#####

logger_multi.info("Finding HU-CP interactions within MPAs")

imatrix = loadInteractionsMatrix(imatrix_path)
cp_in_mpa_i = identifyInteractions(hu_in_mpas, cp_in_mpas, imatrix)


#####
# Prepare and write output tables.
#
# This section:
# - Consolidates output data into dictionaries (o_table_1, o_table_2).
# - Calculates effectiveness scores to scale CPs.
# - Writes the 5 output tables, drawing on new and existing dictionaries.
#####

logger_multi.info("Writing output tables")

o_table_1 = prepareOutputTable1(cp_in_mpa_i, cp_in_mpas)
writeOutputTable1(o_table_1, output1_path, mpa_dict)
joinUIDtoTable1(output1_path, ecoUIDs_path, output1join_path)
o_table_2 = createOutputTable2(o_table_1, cp_area_overlap_dict)
writeOutputTable2(o_table_2, output2_path)
writeOutputTable3(percent_overlap, output3_path) # Percent overlap (slivers) table
createOutputTable4(hu_in_mpas, cp_in_mpas, imatrix, output4_path) # CP/HU list

logger_multi.info('Script complete')