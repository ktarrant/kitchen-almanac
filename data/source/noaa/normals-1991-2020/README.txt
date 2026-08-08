This document describes the technical layout of the CSV normals files in both
the individual, by-station, format and the grouped by-variable format.  It also
provides a guide to the location of the variables within the larger by-variable
tar files.

CONTENTS
Decoding a by-station file
Decoding a by-variable file
Measurement flags
Completeness flags
Variable name definitions
Special notes
-- Concerning percentiles
-- Concerning WMO thresholds
By-variable archive file contents


Decoding a sample monthly by-station file
The (truncated) first two rows of the file USC00053005.csv are:

STATION,LATITUDE,LONGITUDE,ELEVATION,NAME,month,day,hour,MLY-TAVG-NORMAL,
meas_flag_MLY-TAVG-NORMAL,comp_flag_MLY-TAVG-NORMAL,years_MLY-TAVG-NORMAL,...
USC00053005, 40.5764,-105.0858,1525.2,"FT COLLINS, CO US"                    ,
01,99,99,    31.6, ,S,30,...

The first five columns provide the GHCN-daily ID, latitude, longitude, 
elevation, and station name.  The applicable month, day, and hour appear next.
If day or hour are not applicable, the value 99 appears in this field.  An 
additional "date" column may also appear as a composite of the month, day, 
and hour.
The following fields are, in groups of four, a normals quantity, a measurement
flag associated with it, a completeness flag associated with it, and the number
of years used in its calculation.  For this location 30 years of data was used
to compute the January average temperature normal of 31.6.  The measurement and
completeness flags are explained in greater detail below.  At the time of 
initial release this particular file contained 101 different variables meaning 
it had 404 data columns, plus the initial location and date.  Some files for 
seasonal and annual values contain more than 500 variables in over 2100 columns.

Decoding a sample monthly by-variable file
The by-variable CSV files group similar variables for all stations.  A 
comprehensive listing of these is provided below.  For example, the file 
ann-cldd-normal.csv contains the annual cooling degree day normals using 
different base temperatures.  The first two lines of this file are:

GHCN_ID,month,day,hour,ANN-CLDD-NORMAL,meas_flag_ANN-CLDD-NORMAL,
comp_flag_ANN-CLDD-NORMAL,years_ANN-CLDD-NORMAL,ANN-CLDD-BASE40,
meas_flag_ANN-CLDD-BASE40,comp_flag_ANN-CLDD-BASE40,years_ANN-CLDD-BASE40
AQW00061705,99,99,99,  6295.4, ,S,28, 15420.4, ,S,28

The first four data fields contain the GHCN-daily ID, and the applicable month,
day, and hour.  Other station metadata is not included.  Data values are 
provided in groups of four in the same manner as the by-station files described
above.  Thus for this location, the annual base 65 cooling degree day normal 
is 6295.4.  Using a base 40 measure this value is 15420.4.

Measurement Flags
M = Missing
V = Year-round risk of frost-freeze; "too cold to compute"
W = not used
X = Nonzero value has rounded to zero
Y = Insufficient values to perform computation
Z = Computed valued created logical inconsistency with other values

Completeness Flags
S = Standard - meets WMO standards for data availability for 24 or more years 
(missing months are filled with estimates based on surrounding stations where 
available)
R = Representative - meets WMO standards for data availability for 10 or more 
years 	(missing months are filled with estimates based on surrounding stations)
P = Provisional - meets WMO standards for data availability for 10 or more 
years (missing months cannot be filled due to lack of surrounding stations)
E = Estimated - meets WMO standards for data availability for 2 or more years 
for all months (nearby stations with standard normals are available to estimate 
normals statistically)

  
Decoding the variable names
Variable names consist of either 15 or 23 characters.  The first three indicate 
the timing element.  The following are possible:
MLY, DLY, HLY = monthly, daily, hourly
DJF, MAM, JJA, SON = seasonal, e.g. MAM is March-April-May
ANN, MTD, YTD = annual, month-to-date, year-to-date

Characters 5-8 indicate the meteorological element. The following are available:
TMIN, TMAX  = minimum and maximum temperature
TAVG, DUTR  = average temperature, diurnal temperature range
CLDD, HTDD  = cooling and heating degree days
GRDD        = growing degree days
PRCP        = precipitation
SNOW, SNWD  = snow and snow depth

These variables are exclusive to the hourly normals:
TEMP, DEWP = temperature and dew point
HIDX, WCHL = heat index and wind chill
PRES, WIND = pressure and wind
CLDH, HTDH = cooling and heating degree hours
CLOD       = cloud cover

Characters 10-15 indicate the type of statistic.  If present, characters 16-23 
will give more information, typically a threshold value, about the statistic.

The types of statistics are:
NORMAL = long term average
STDDEV = long term standard deviation
AVGNDS = average number of days meeting criteria given
TOBADJ = time of observation bias adjustment

BASE40 = with degree days, the base temperature.
BASE45   Note that NORMAL with degree days is base 65.
BASE50
BASE55
BASE57
BASE60
BASE70
BASE72

TB4886 = Temperature bounded growing degree days. 48 to 86.
TB5086 = Temperature bounded growing degree days. 50 to 86.

PCTALL = Probability of meeting threshold in 29-day window
         centered on date.  Used for precipitation elements.

PRBFST = Latest date on which the first frost-freeze of the cold
         season will occur at the given probability and temperature 
         threshold
PRBLST = Earliest date on which the last frost-freeze of the cold 
         season will occur given probability and temperature
         threshold
PRBGSL = Length of growing season with given probability and
         temperature threshold

PRBOCC = Probability of occurrence of given minimum temperature or
         lower

QUAR01 = First quartile  (25%)
QUAR02 = Second quartile (50%)
QUAR03 = Third quartile  (75%)
QUIN01 = First quintile  (20%)
QUIN02 = Second quintile (40%)
QUIN03 = Third quintile  (60%)
QUIN04 = Fourth quintile (80%)
TERC01 = First tercile   (33%)
TERC02 = Second tercile  (67%)

The following are for hourly normals only
10PCTL = 10th percentile
90PCTL = 90th percentile
AVGSPD = Average wind speed
PCTCLM = Percentage of calm wind occurrences
1STDIR = Modal wind direction (1-8) in octants clockwise from north
1STPCT = Percentage of cases from modal direction
2NDDIR = Second mode of wind direction
2NDPCT = Percentage of cases from second modal direction
VCTDIR = Average wind vector direction
VCTSPD = Magnitude of average wind vector

PCTCLR = Percentage occurrence of clouds clear
PCTFEW = Percentage occurrence of clouds few
PCTSCT = Percentage occurrence of clouds scattered
PCTBKN = Percentage occurrence of clouds broken
PCTOVC = Percentage occurrence of clouds overcast

The additional information fields for temperature normals (with the exception 
of agricultural normals) take the form GRTHnnn and LSTHnnn corresponding to 
values greater/less than or equal to the value nnn.  Units of nnn are whole 
degrees Fahrenheit.
Example: JJA-TMAX-AVGNDS-GRTH090 is the average number of days in the months 
of June, July, and August for which the maximum temperature is greater than 
or equal to 90.

The additional information fields for precipitation elements take the form 
GEnnnuu in which nnn is a value and uu are the units.  Possible values for 
units are HI (hundredths of an inch), TI (tenths of an inch), 
WI (whole inches), and MM (millimeters).
Example: ANN-SNOW-AVGNDS-GE001TI is the annual average number of days with 
snowfall greater than or equal 0.1 inch.

The additional information fields for agricultural normals provide a 
temperature threshold and probability in the form TnnFPmm where nn is the 
temperature and mm is the probability.
Example: ANN-TMIN-PRBFST-T32FP10 provides the earliest date at which there is a 
10% probability of a temperature of 32 or less.

Special note concerning percentiles
Certain precipitation group quantile values appear differently between the 
by-variable and by-station versions.  The ordered quartiles (QUAR01, QUAR02, 
QUAR03) in the by-variable files have been converted to percentiles (25PCTL, 
50PCTL, 75PCTL) in the by-station files.  Similar conversions occur for 
quintiles (QUIN) and terciles (TERC).

Special note concerning WMO temperature threshold normals
The by-variable temperature files contain a secondary set of normals computed 
specifically for the WMO.  These appear with an annotation "_wmo" in the file 
name.  These average number of days of the maximum temperature being greater 
than or equal to 25, 30, 35, and 40 deg C appear as the following, with the 
threshold appearing 1 degree lower than its actual value for programmatic 
reasons.
MLY-TMAX-AVGNDS-GRTH076
MLY-TMAX-AVGNDS-GRTH085
MLY-TMAX-AVGNDS-GRTH094
MLY-TMAX-AVGNDS-GRTH103
The test for temperatures below but not equal to freezing (0 C) similarly 
appears as a threshold one Fahrenheit degree lower than its actual value.
MLY-TMAX-AVGNDS-LSTH031
MLY-TMIN-AVGNDS-LSTH031


ARCHIVE FILE CONTENTS
The by-station CSV files will contain whichever variables that could be computed
for that station and time period.  The by-station tar files contain collections 
of these stations.  The by-variable CSV files and their contents follow.

Each by-variable tar file also contains an inventory indicating which stations
are available.  Note, however, that stations appearing in this list might not 
have all variables.  For example, in the monthly precipitation group, a station 
could be present for liquid precipitation only and not snow or snowdepth.

Examples of the archive file names shown are for a near final processing run.  
The actual files provided may have later dates (cYYYYMMDD) reflecting updates 
or the timing of the 2006-2020 period of record.  For each tar.gz file the 
listing of its member CSV files is given.  Then for each of these CSV files, 
the variable names contained therein are provided. 
================================
us-climate-normals_1991-2020_monthly_temperature_by-variable_c20210419.tar.gz
=================================
ann-cldd-normal.csv
ann-grdd-normal.csv
ann-htdd-normal.csv
ann-normal-allall.csv
ann-tmax-avgnds.csv
ann-tmax-avgnds_wmo.csv
ann-tmin-avgnds.csv
ann-tmin-avgnds_wmo.csv
ann-tmin-prbfst-t16.csv
ann-tmin-prbfst-t20.csv
ann-tmin-prbfst-t24.csv
ann-tmin-prbfst-t28.csv
ann-tmin-prbfst-t32.csv
ann-tmin-prbfst-t36.csv
ann-tmin-prbgsl-t16.csv
ann-tmin-prbgsl-t20.csv
ann-tmin-prbgsl-t24.csv
ann-tmin-prbgsl-t28.csv
ann-tmin-prbgsl-t32.csv
ann-tmin-prbgsl-t36.csv
ann-tmin-prblst-t16.csv
ann-tmin-prblst-t20.csv
ann-tmin-prblst-t24.csv
ann-tmin-prblst-t28.csv
ann-tmin-prblst-t32.csv
ann-tmin-prblst-t36.csv
ann-tmin-prbocc.csv
djf-cldd-normal.csv
djf-grdd-normal.csv
djf-htdd-normal.csv
djf-normal-allall.csv
djf-tmax-avgnds.csv
djf-tmax-avgnds_wmo.csv
djf-tmin-avgnds.csv
djf-tmin-avgnds_wmo.csv
jja-cldd-normal.csv
jja-grdd-normal.csv
jja-htdd-normal.csv
jja-normal-allall.csv
jja-tmax-avgnds.csv
jja-tmax-avgnds_wmo.csv
jja-tmin-avgnds.csv
jja-tmin-avgnds_wmo.csv
mam-cldd-normal.csv
mam-grdd-normal.csv
mam-htdd-normal.csv
mam-normal-allall.csv
mam-tmax-avgnds.csv
mam-tmax-avgnds_wmo.csv
mam-tmin-avgnds.csv
mam-tmin-avgnds_wmo.csv
mly-cldd-normal.csv
mly-grdd-normal.csv
mly-htdd-normal.csv
mly-normal-allall.csv
mly-stddev-allall.csv
mly-tmax-avgnds.csv
mly-tmax-avgnds_wmo.csv
mly-tmax-tobadj.csv
mly-tmin-avgnds.csv
mly-tmin-avgnds_wmo.csv
mly-tmin-prbocc.csv
mly-tmin-tobadj.csv
son-cldd-normal.csv
son-grdd-normal.csv
son-htdd-normal.csv
son-normal-allall.csv
son-tmax-avgnds.csv
son-tmax-avgnds_wmo.csv
son-tmin-avgnds.csv
son-tmin-avgnds_wmo.csv
----- ann-cldd-normal.csv -----
ANN-CLDD-NORMAL
ANN-CLDD-BASE40
ANN-CLDD-BASE45
ANN-CLDD-BASE50
ANN-CLDD-BASE55
ANN-CLDD-BASE57
ANN-CLDD-BASE60
ANN-CLDD-BASE70
ANN-CLDD-BASE72
----- ann-grdd-normal.csv -----
ANN-GRDD-NORMAL
ANN-GRDD-BASE40
ANN-GRDD-BASE45
ANN-GRDD-BASE50
ANN-GRDD-BASE55
ANN-GRDD-BASE57
ANN-GRDD-BASE60
ANN-GRDD-BASE70
ANN-GRDD-BASE72
ANN-GRDD-TB4886
ANN-GRDD-TB5086
----- ann-htdd-normal.csv -----
ANN-HTDD-NORMAL
ANN-HTDD-BASE40
ANN-HTDD-BASE45
ANN-HTDD-BASE50
ANN-HTDD-BASE55
ANN-HTDD-BASE57
ANN-HTDD-BASE60
----- ann-normal-allall.csv -----
ANN-TAVG-NORMAL
ANN-TMIN-NORMAL
ANN-TMAX-NORMAL
ANN-DUTR-NORMAL
----- ann-tmax-avgnds.csv -----
ANN-TMAX-AVGNDS-GRTH032
ANN-TMAX-AVGNDS-GRTH040
ANN-TMAX-AVGNDS-GRTH050
ANN-TMAX-AVGNDS-GRTH060
ANN-TMAX-AVGNDS-GRTH070
ANN-TMAX-AVGNDS-GRTH080
ANN-TMAX-AVGNDS-GRTH090
ANN-TMAX-AVGNDS-GRTH100
ANN-TMAX-AVGNDS-LSTH032
----- ann-tmax-avgnds_wmo.csv -----
ANN-TMAX-AVGNDS-GRTH076
ANN-TMAX-AVGNDS-GRTH085
ANN-TMAX-AVGNDS-GRTH094
ANN-TMAX-AVGNDS-GRTH103
ANN-TMAX-AVGNDS-LSTH031
----- ann-tmin-avgnds.csv -----
ANN-TMIN-AVGNDS-LSTH000
ANN-TMIN-AVGNDS-LSTH010
ANN-TMIN-AVGNDS-LSTH020
ANN-TMIN-AVGNDS-LSTH032
ANN-TMIN-AVGNDS-LSTH040
ANN-TMIN-AVGNDS-LSTH050
ANN-TMIN-AVGNDS-LSTH060
ANN-TMIN-AVGNDS-LSTH070
----- ann-tmin-avgnds_wmo.csv -----
ANN-TMIN-AVGNDS-LSTH031
----- ann-tmin-prbfst-t16.csv -----
ANN-TMIN-PRBFST-T16FP10
ANN-TMIN-PRBFST-T16FP20
ANN-TMIN-PRBFST-T16FP30
ANN-TMIN-PRBFST-T16FP40
ANN-TMIN-PRBFST-T16FP50
ANN-TMIN-PRBFST-T16FP60
ANN-TMIN-PRBFST-T16FP70
ANN-TMIN-PRBFST-T16FP80
ANN-TMIN-PRBFST-T16FP90
----- ann-tmin-prbfst-t20.csv -----
ANN-TMIN-PRBFST-T20FP10
ANN-TMIN-PRBFST-T20FP20
ANN-TMIN-PRBFST-T20FP30
ANN-TMIN-PRBFST-T20FP40
ANN-TMIN-PRBFST-T20FP50
ANN-TMIN-PRBFST-T20FP60
ANN-TMIN-PRBFST-T20FP70
ANN-TMIN-PRBFST-T20FP80
ANN-TMIN-PRBFST-T20FP90
----- ann-tmin-prbfst-t24.csv -----
ANN-TMIN-PRBFST-T24FP10
ANN-TMIN-PRBFST-T24FP20
ANN-TMIN-PRBFST-T24FP30
ANN-TMIN-PRBFST-T24FP40
ANN-TMIN-PRBFST-T24FP50
ANN-TMIN-PRBFST-T24FP60
ANN-TMIN-PRBFST-T24FP70
ANN-TMIN-PRBFST-T24FP80
ANN-TMIN-PRBFST-T24FP90
----- ann-tmin-prbfst-t28.csv -----
ANN-TMIN-PRBFST-T28FP10
ANN-TMIN-PRBFST-T28FP20
ANN-TMIN-PRBFST-T28FP30
ANN-TMIN-PRBFST-T28FP40
ANN-TMIN-PRBFST-T28FP50
ANN-TMIN-PRBFST-T28FP60
ANN-TMIN-PRBFST-T28FP70
ANN-TMIN-PRBFST-T28FP80
ANN-TMIN-PRBFST-T28FP90
----- ann-tmin-prbfst-t32.csv -----
ANN-TMIN-PRBFST-T32FP10
ANN-TMIN-PRBFST-T32FP20
ANN-TMIN-PRBFST-T32FP30
ANN-TMIN-PRBFST-T32FP40
ANN-TMIN-PRBFST-T32FP50
ANN-TMIN-PRBFST-T32FP60
ANN-TMIN-PRBFST-T32FP70
ANN-TMIN-PRBFST-T32FP80
ANN-TMIN-PRBFST-T32FP90
----- ann-tmin-prbfst-t36.csv -----
ANN-TMIN-PRBFST-T36FP10
ANN-TMIN-PRBFST-T36FP20
ANN-TMIN-PRBFST-T36FP30
ANN-TMIN-PRBFST-T36FP40
ANN-TMIN-PRBFST-T36FP50
ANN-TMIN-PRBFST-T36FP60
ANN-TMIN-PRBFST-T36FP70
ANN-TMIN-PRBFST-T36FP80
ANN-TMIN-PRBFST-T36FP90
----- ann-tmin-prbgsl-t16.csv -----
ANN-TMIN-PRBGSL-T16FP10
ANN-TMIN-PRBGSL-T16FP20
ANN-TMIN-PRBGSL-T16FP30
ANN-TMIN-PRBGSL-T16FP40
ANN-TMIN-PRBGSL-T16FP50
ANN-TMIN-PRBGSL-T16FP60
ANN-TMIN-PRBGSL-T16FP70
ANN-TMIN-PRBGSL-T16FP80
ANN-TMIN-PRBGSL-T16FP90
----- ann-tmin-prbgsl-t20.csv -----
ANN-TMIN-PRBGSL-T20FP10
ANN-TMIN-PRBGSL-T20FP20
ANN-TMIN-PRBGSL-T20FP30
ANN-TMIN-PRBGSL-T20FP40
ANN-TMIN-PRBGSL-T20FP50
ANN-TMIN-PRBGSL-T20FP60
ANN-TMIN-PRBGSL-T20FP70
ANN-TMIN-PRBGSL-T20FP80
ANN-TMIN-PRBGSL-T20FP90
----- ann-tmin-prbgsl-t24.csv -----
ANN-TMIN-PRBGSL-T24FP10
ANN-TMIN-PRBGSL-T24FP20
ANN-TMIN-PRBGSL-T24FP30
ANN-TMIN-PRBGSL-T24FP40
ANN-TMIN-PRBGSL-T24FP50
ANN-TMIN-PRBGSL-T24FP60
ANN-TMIN-PRBGSL-T24FP70
ANN-TMIN-PRBGSL-T24FP80
ANN-TMIN-PRBGSL-T24FP90
----- ann-tmin-prbgsl-t28.csv -----
ANN-TMIN-PRBGSL-T28FP10
ANN-TMIN-PRBGSL-T28FP20
ANN-TMIN-PRBGSL-T28FP30
ANN-TMIN-PRBGSL-T28FP40
ANN-TMIN-PRBGSL-T28FP50
ANN-TMIN-PRBGSL-T28FP60
ANN-TMIN-PRBGSL-T28FP70
ANN-TMIN-PRBGSL-T28FP80
ANN-TMIN-PRBGSL-T28FP90
----- ann-tmin-prbgsl-t32.csv -----
ANN-TMIN-PRBGSL-T32FP10
ANN-TMIN-PRBGSL-T32FP20
ANN-TMIN-PRBGSL-T32FP30
ANN-TMIN-PRBGSL-T32FP40
ANN-TMIN-PRBGSL-T32FP50
ANN-TMIN-PRBGSL-T32FP60
ANN-TMIN-PRBGSL-T32FP70
ANN-TMIN-PRBGSL-T32FP80
ANN-TMIN-PRBGSL-T32FP90
----- ann-tmin-prbgsl-t36.csv -----
ANN-TMIN-PRBGSL-T36FP10
ANN-TMIN-PRBGSL-T36FP20
ANN-TMIN-PRBGSL-T36FP30
ANN-TMIN-PRBGSL-T36FP40
ANN-TMIN-PRBGSL-T36FP50
ANN-TMIN-PRBGSL-T36FP60
ANN-TMIN-PRBGSL-T36FP70
ANN-TMIN-PRBGSL-T36FP80
ANN-TMIN-PRBGSL-T36FP90
----- ann-tmin-prblst-t16.csv -----
ANN-TMIN-PRBLST-T16FP10
ANN-TMIN-PRBLST-T16FP20
ANN-TMIN-PRBLST-T16FP30
ANN-TMIN-PRBLST-T16FP40
ANN-TMIN-PRBLST-T16FP50
ANN-TMIN-PRBLST-T16FP60
ANN-TMIN-PRBLST-T16FP70
ANN-TMIN-PRBLST-T16FP80
ANN-TMIN-PRBLST-T16FP90
----- ann-tmin-prblst-t20.csv -----
ANN-TMIN-PRBLST-T20FP10
ANN-TMIN-PRBLST-T20FP20
ANN-TMIN-PRBLST-T20FP30
ANN-TMIN-PRBLST-T20FP40
ANN-TMIN-PRBLST-T20FP50
ANN-TMIN-PRBLST-T20FP60
ANN-TMIN-PRBLST-T20FP70
ANN-TMIN-PRBLST-T20FP80
ANN-TMIN-PRBLST-T20FP90
----- ann-tmin-prblst-t24.csv -----
ANN-TMIN-PRBLST-T24FP10
ANN-TMIN-PRBLST-T24FP20
ANN-TMIN-PRBLST-T24FP30
ANN-TMIN-PRBLST-T24FP40
ANN-TMIN-PRBLST-T24FP50
ANN-TMIN-PRBLST-T24FP60
ANN-TMIN-PRBLST-T24FP70
ANN-TMIN-PRBLST-T24FP80
ANN-TMIN-PRBLST-T24FP90
----- ann-tmin-prblst-t28.csv -----
ANN-TMIN-PRBLST-T28FP10
ANN-TMIN-PRBLST-T28FP20
ANN-TMIN-PRBLST-T28FP30
ANN-TMIN-PRBLST-T28FP40
ANN-TMIN-PRBLST-T28FP50
ANN-TMIN-PRBLST-T28FP60
ANN-TMIN-PRBLST-T28FP70
ANN-TMIN-PRBLST-T28FP80
ANN-TMIN-PRBLST-T28FP90
----- ann-tmin-prblst-t32.csv -----
ANN-TMIN-PRBLST-T32FP10
ANN-TMIN-PRBLST-T32FP20
ANN-TMIN-PRBLST-T32FP30
ANN-TMIN-PRBLST-T32FP40
ANN-TMIN-PRBLST-T32FP50
ANN-TMIN-PRBLST-T32FP60
ANN-TMIN-PRBLST-T32FP70
ANN-TMIN-PRBLST-T32FP80
ANN-TMIN-PRBLST-T32FP90
----- ann-tmin-prblst-t36.csv -----
ANN-TMIN-PRBLST-T36FP10
ANN-TMIN-PRBLST-T36FP20
ANN-TMIN-PRBLST-T36FP30
ANN-TMIN-PRBLST-T36FP40
ANN-TMIN-PRBLST-T36FP50
ANN-TMIN-PRBLST-T36FP60
ANN-TMIN-PRBLST-T36FP70
ANN-TMIN-PRBLST-T36FP80
ANN-TMIN-PRBLST-T36FP90
----- ann-tmin-prbocc.csv -----
ANN-TMIN-PRBOCC-LSTH016
ANN-TMIN-PRBOCC-LSTH020
ANN-TMIN-PRBOCC-LSTH024
ANN-TMIN-PRBOCC-LSTH028
ANN-TMIN-PRBOCC-LSTH032
ANN-TMIN-PRBOCC-LSTH036
----- djf-cldd-normal.csv -----
DJF-CLDD-NORMAL
DJF-CLDD-BASE40
DJF-CLDD-BASE45
DJF-CLDD-BASE50
DJF-CLDD-BASE55
DJF-CLDD-BASE57
DJF-CLDD-BASE60
DJF-CLDD-BASE70
DJF-CLDD-BASE72
----- djf-grdd-normal.csv -----
DJF-GRDD-NORMAL
DJF-GRDD-BASE40
DJF-GRDD-BASE45
DJF-GRDD-BASE50
DJF-GRDD-BASE55
DJF-GRDD-BASE57
DJF-GRDD-BASE60
DJF-GRDD-BASE70
DJF-GRDD-BASE72
DJF-GRDD-TB4886
DJF-GRDD-TB5086
----- djf-htdd-normal.csv -----
DJF-HTDD-NORMAL
DJF-HTDD-BASE40
DJF-HTDD-BASE45
DJF-HTDD-BASE50
DJF-HTDD-BASE55
DJF-HTDD-BASE57
DJF-HTDD-BASE60
----- djf-normal-allall.csv -----
DJF-TAVG-NORMAL
DJF-TMIN-NORMAL
DJF-TMAX-NORMAL
DJF-DUTR-NORMAL
----- djf-tmax-avgnds.csv -----
DJF-TMAX-AVGNDS-GRTH032
DJF-TMAX-AVGNDS-GRTH040
DJF-TMAX-AVGNDS-GRTH050
DJF-TMAX-AVGNDS-GRTH060
DJF-TMAX-AVGNDS-GRTH070
DJF-TMAX-AVGNDS-GRTH080
DJF-TMAX-AVGNDS-GRTH090
DJF-TMAX-AVGNDS-GRTH100
DJF-TMAX-AVGNDS-LSTH032
----- djf-tmax-avgnds_wmo.csv -----
DJF-TMAX-AVGNDS-GRTH076
DJF-TMAX-AVGNDS-GRTH085
DJF-TMAX-AVGNDS-GRTH094
DJF-TMAX-AVGNDS-GRTH103
DJF-TMAX-AVGNDS-LSTH031
----- djf-tmin-avgnds.csv -----
DJF-TMIN-AVGNDS-LSTH000
DJF-TMIN-AVGNDS-LSTH010
DJF-TMIN-AVGNDS-LSTH020
DJF-TMIN-AVGNDS-LSTH032
DJF-TMIN-AVGNDS-LSTH040
DJF-TMIN-AVGNDS-LSTH050
DJF-TMIN-AVGNDS-LSTH060
DJF-TMIN-AVGNDS-LSTH070
----- djf-tmin-avgnds_wmo.csv -----
DJF-TMIN-AVGNDS-LSTH031
----- jja-cldd-normal.csv -----
JJA-CLDD-NORMAL
JJA-CLDD-BASE40
JJA-CLDD-BASE45
JJA-CLDD-BASE50
JJA-CLDD-BASE55
JJA-CLDD-BASE57
JJA-CLDD-BASE60
JJA-CLDD-BASE70
JJA-CLDD-BASE72
----- jja-grdd-normal.csv -----
JJA-GRDD-NORMAL
JJA-GRDD-BASE40
JJA-GRDD-BASE45
JJA-GRDD-BASE50
JJA-GRDD-BASE55
JJA-GRDD-BASE57
JJA-GRDD-BASE60
JJA-GRDD-BASE70
JJA-GRDD-BASE72
JJA-GRDD-TB4886
JJA-GRDD-TB5086
----- jja-htdd-normal.csv -----
JJA-HTDD-NORMAL
JJA-HTDD-BASE40
JJA-HTDD-BASE45
JJA-HTDD-BASE50
JJA-HTDD-BASE55
JJA-HTDD-BASE57
JJA-HTDD-BASE60
----- jja-normal-allall.csv -----
JJA-TAVG-NORMAL
JJA-TMIN-NORMAL
JJA-TMAX-NORMAL
JJA-DUTR-NORMAL
----- jja-tmax-avgnds.csv -----
JJA-TMAX-AVGNDS-GRTH032
JJA-TMAX-AVGNDS-GRTH040
JJA-TMAX-AVGNDS-GRTH050
JJA-TMAX-AVGNDS-GRTH060
JJA-TMAX-AVGNDS-GRTH070
JJA-TMAX-AVGNDS-GRTH080
JJA-TMAX-AVGNDS-GRTH090
JJA-TMAX-AVGNDS-GRTH100
JJA-TMAX-AVGNDS-LSTH032
----- jja-tmax-avgnds_wmo.csv -----
JJA-TMAX-AVGNDS-GRTH076
JJA-TMAX-AVGNDS-GRTH085
JJA-TMAX-AVGNDS-GRTH094
JJA-TMAX-AVGNDS-GRTH103
JJA-TMAX-AVGNDS-LSTH031
----- jja-tmin-avgnds.csv -----
JJA-TMIN-AVGNDS-LSTH000
JJA-TMIN-AVGNDS-LSTH010
JJA-TMIN-AVGNDS-LSTH020
JJA-TMIN-AVGNDS-LSTH032
JJA-TMIN-AVGNDS-LSTH040
JJA-TMIN-AVGNDS-LSTH050
JJA-TMIN-AVGNDS-LSTH060
JJA-TMIN-AVGNDS-LSTH070
----- jja-tmin-avgnds_wmo.csv -----
JJA-TMIN-AVGNDS-LSTH031
----- mam-cldd-normal.csv -----
MAM-CLDD-NORMAL
MAM-CLDD-BASE40
MAM-CLDD-BASE45
MAM-CLDD-BASE50
MAM-CLDD-BASE55
MAM-CLDD-BASE57
MAM-CLDD-BASE60
MAM-CLDD-BASE70
MAM-CLDD-BASE72
----- mam-grdd-normal.csv -----
MAM-GRDD-NORMAL
MAM-GRDD-BASE40
MAM-GRDD-BASE45
MAM-GRDD-BASE50
MAM-GRDD-BASE55
MAM-GRDD-BASE57
MAM-GRDD-BASE60
MAM-GRDD-BASE70
MAM-GRDD-BASE72
MAM-GRDD-TB4886
MAM-GRDD-TB5086
----- mam-htdd-normal.csv -----
MAM-HTDD-NORMAL
MAM-HTDD-BASE40
MAM-HTDD-BASE45
MAM-HTDD-BASE50
MAM-HTDD-BASE55
MAM-HTDD-BASE57
MAM-HTDD-BASE60
----- mam-normal-allall.csv -----
MAM-TAVG-NORMAL
MAM-TMIN-NORMAL
MAM-TMAX-NORMAL
MAM-DUTR-NORMAL
----- mam-tmax-avgnds.csv -----
MAM-TMAX-AVGNDS-GRTH032
MAM-TMAX-AVGNDS-GRTH040
MAM-TMAX-AVGNDS-GRTH050
MAM-TMAX-AVGNDS-GRTH060
MAM-TMAX-AVGNDS-GRTH070
MAM-TMAX-AVGNDS-GRTH080
MAM-TMAX-AVGNDS-GRTH090
MAM-TMAX-AVGNDS-GRTH100
MAM-TMAX-AVGNDS-LSTH032
----- mam-tmax-avgnds_wmo.csv -----
MAM-TMAX-AVGNDS-GRTH076
MAM-TMAX-AVGNDS-GRTH085
MAM-TMAX-AVGNDS-GRTH094
MAM-TMAX-AVGNDS-GRTH103
MAM-TMAX-AVGNDS-LSTH031
----- mam-tmin-avgnds.csv -----
MAM-TMIN-AVGNDS-LSTH000
MAM-TMIN-AVGNDS-LSTH010
MAM-TMIN-AVGNDS-LSTH020
MAM-TMIN-AVGNDS-LSTH032
MAM-TMIN-AVGNDS-LSTH040
MAM-TMIN-AVGNDS-LSTH050
MAM-TMIN-AVGNDS-LSTH060
MAM-TMIN-AVGNDS-LSTH070
----- mam-tmin-avgnds_wmo.csv -----
MAM-TMIN-AVGNDS-LSTH031
----- mly-cldd-normal.csv -----
MLY-CLDD-NORMAL
MLY-CLDD-BASE40
MLY-CLDD-BASE45
MLY-CLDD-BASE50
MLY-CLDD-BASE55
MLY-CLDD-BASE57
MLY-CLDD-BASE60
MLY-CLDD-BASE70
MLY-CLDD-BASE72
----- mly-grdd-normal.csv -----
MLY-GRDD-NORMAL
MLY-GRDD-BASE40
MLY-GRDD-BASE45
MLY-GRDD-BASE50
MLY-GRDD-BASE55
MLY-GRDD-BASE57
MLY-GRDD-BASE60
MLY-GRDD-BASE70
MLY-GRDD-BASE72
MLY-GRDD-TB4886
MLY-GRDD-TB5086
----- mly-htdd-normal.csv -----
MLY-HTDD-NORMAL
MLY-HTDD-BASE40
MLY-HTDD-BASE45
MLY-HTDD-BASE50
MLY-HTDD-BASE55
MLY-HTDD-BASE57
MLY-HTDD-BASE60
----- mly-normal-allall.csv -----
MLY-TAVG-NORMAL
MLY-TMAX-NORMAL
MLY-TMIN-NORMAL
MLY-DUTR-NORMAL
----- mly-stddev-allall.csv -----
MLY-TAVG-STDDEV
MLY-TMAX-STDDEV
MLY-TMIN-STDDEV
MLY-DUTR-STDDEV
----- mly-tmax-avgnds.csv -----
MLY-TMAX-AVGNDS-GRTH032
MLY-TMAX-AVGNDS-GRTH040
MLY-TMAX-AVGNDS-GRTH050
MLY-TMAX-AVGNDS-GRTH060
MLY-TMAX-AVGNDS-GRTH070
MLY-TMAX-AVGNDS-GRTH080
MLY-TMAX-AVGNDS-GRTH090
MLY-TMAX-AVGNDS-GRTH100
MLY-TMAX-AVGNDS-LSTH032
----- mly-tmax-avgnds_wmo.csv -----
MLY-TMAX-AVGNDS-GRTH076
MLY-TMAX-AVGNDS-GRTH085
MLY-TMAX-AVGNDS-GRTH094
MLY-TMAX-AVGNDS-GRTH103
MLY-TMAX-AVGNDS-LSTH031
----- mly-tmax-tobadj.csv -----
MLY-TMAX-TOBADJ
----- mly-tmin-avgnds.csv -----
MLY-TMIN-AVGNDS-LSTH000
MLY-TMIN-AVGNDS-LSTH010
MLY-TMIN-AVGNDS-LSTH020
MLY-TMIN-AVGNDS-LSTH032
MLY-TMIN-AVGNDS-LSTH040
MLY-TMIN-AVGNDS-LSTH050
MLY-TMIN-AVGNDS-LSTH060
MLY-TMIN-AVGNDS-LSTH070
----- mly-tmin-avgnds_wmo.csv -----
MLY-TMIN-AVGNDS-LSTH031
----- mly-tmin-prbocc.csv -----
MLY-TMIN-PRBOCC-LSTH016
MLY-TMIN-PRBOCC-LSTH020
MLY-TMIN-PRBOCC-LSTH024
MLY-TMIN-PRBOCC-LSTH028
MLY-TMIN-PRBOCC-LSTH032
MLY-TMIN-PRBOCC-LSTH036
----- mly-tmin-tobadj.csv -----
MLY-TMIN-TOBADJ
----- son-cldd-normal.csv -----
SON-CLDD-NORMAL
SON-CLDD-BASE40
SON-CLDD-BASE45
SON-CLDD-BASE50
SON-CLDD-BASE55
SON-CLDD-BASE57
SON-CLDD-BASE60
SON-CLDD-BASE70
SON-CLDD-BASE72
----- son-grdd-normal.csv -----
SON-GRDD-NORMAL
SON-GRDD-BASE40
SON-GRDD-BASE45
SON-GRDD-BASE50
SON-GRDD-BASE55
SON-GRDD-BASE57
SON-GRDD-BASE60
SON-GRDD-BASE70
SON-GRDD-BASE72
SON-GRDD-TB4886
SON-GRDD-TB5086
----- son-htdd-normal.csv -----
SON-HTDD-NORMAL
SON-HTDD-BASE40
SON-HTDD-BASE45
SON-HTDD-BASE50
SON-HTDD-BASE55
SON-HTDD-BASE57
SON-HTDD-BASE60
----- son-normal-allall.csv -----
SON-TAVG-NORMAL
SON-TMIN-NORMAL
SON-TMAX-NORMAL
SON-DUTR-NORMAL
----- son-tmax-avgnds.csv -----
SON-TMAX-AVGNDS-GRTH032
SON-TMAX-AVGNDS-GRTH040
SON-TMAX-AVGNDS-GRTH050
SON-TMAX-AVGNDS-GRTH060
SON-TMAX-AVGNDS-GRTH070
SON-TMAX-AVGNDS-GRTH080
SON-TMAX-AVGNDS-GRTH090
SON-TMAX-AVGNDS-GRTH100
SON-TMAX-AVGNDS-LSTH032
----- son-tmax-avgnds_wmo.csv -----
SON-TMAX-AVGNDS-GRTH076
SON-TMAX-AVGNDS-GRTH085
SON-TMAX-AVGNDS-GRTH094
SON-TMAX-AVGNDS-GRTH103
SON-TMAX-AVGNDS-LSTH031
----- son-tmin-avgnds.csv -----
SON-TMIN-AVGNDS-LSTH000
SON-TMIN-AVGNDS-LSTH010
SON-TMIN-AVGNDS-LSTH020
SON-TMIN-AVGNDS-LSTH032
SON-TMIN-AVGNDS-LSTH040
SON-TMIN-AVGNDS-LSTH050
SON-TMIN-AVGNDS-LSTH060
SON-TMIN-AVGNDS-LSTH070
----- son-tmin-avgnds_wmo.csv -----
SON-TMIN-AVGNDS-LSTH031
=================================
us-climate-normals_1991-2020_daily_temperature_by-variable_c20210419.tar.gz
=================================
dly-cldd-normal.csv
dly-grdd-normal.csv
dly-htdd-normal.csv
dly-temp-normal.csv
dly-temp-stddev.csv
----- dly-cldd-normal.csv -----
DLY-CLDD-NORMAL
DLY-CLDD-BASE40
DLY-CLDD-BASE45
DLY-CLDD-BASE50
DLY-CLDD-BASE55
DLY-CLDD-BASE57
DLY-CLDD-BASE60
DLY-CLDD-BASE70
DLY-CLDD-BASE72
----- dly-grdd-normal.csv -----
DLY-GRDD-NORMAL
DLY-GRDD-BASE40
DLY-GRDD-BASE45
DLY-GRDD-BASE50
DLY-GRDD-BASE55
DLY-GRDD-BASE57
DLY-GRDD-BASE60
DLY-GRDD-BASE70
DLY-GRDD-BASE72
DLY-GRDD-TB4886
DLY-GRDD-TB5086
----- dly-htdd-normal.csv -----
DLY-HTDD-NORMAL
DLY-HTDD-BASE40
DLY-HTDD-BASE45
DLY-HTDD-BASE50
DLY-HTDD-BASE55
DLY-HTDD-BASE57
DLY-HTDD-BASE60
----- dly-temp-normal.csv -----
DLY-TAVG-NORMAL
DLY-TMAX-NORMAL
DLY-TMIN-NORMAL
DLY-DUTR-NORMAL
----- dly-temp-stddev.csv -----
DLY-TAVG-STDDEV
DLY-TMAX-STDDEV
DLY-TMIN-STDDEV
DLY-DUTR-STDDEV
=================================
us-climate-normals_1991-2020_monthly_precipitation_by-variable_c20210412.tar.gz
=================================
ann-prcp-avgnds-custom-30yr.csv
ann-prcp-avgnds-metric-30yr.csv
ann-snow-avgnds-custom-30yr.csv
ann-snow-avgnds-metric-30yr.csv
ann-snwd-avgnds-custom-30yr.csv
ann-snwd-avgnds-metric-30yr.csv
djf-prcp-avgnds-custom-30yr.csv
djf-prcp-avgnds-metric-30yr.csv
djf-snow-avgnds-custom-30yr.csv
djf-snow-avgnds-metric-30yr.csv
djf-snwd-avgnds-custom-30yr.csv
djf-snwd-avgnds-metric-30yr.csv
jja-prcp-avgnds-custom-30yr.csv
jja-prcp-avgnds-metric-30yr.csv
jja-snow-avgnds-custom-30yr.csv
jja-snow-avgnds-metric-30yr.csv
jja-snwd-avgnds-custom-30yr.csv
jja-snwd-avgnds-metric-30yr.csv
mam-prcp-avgnds-custom-30yr.csv
mam-prcp-avgnds-metric-30yr.csv
mam-snow-avgnds-custom-30yr.csv
mam-snow-avgnds-metric-30yr.csv
mam-snwd-avgnds-custom-30yr.csv
mam-snwd-avgnds-metric-30yr.csv
mly-prcp-avgnds-custom-30yr.csv
mly-prcp-avgnds-metric-30yr.csv
mly-prcp-normal-custom-30yr.csv
mly-prcp-normal-metric-30yr.csv
mly-prcp-quantl-custom-30yr.csv
mly-prcp-quantl-metric-30yr.csv
mly-snow-avgnds-custom-30yr.csv
mly-snow-avgnds-metric-30yr.csv
mly-snow-normal-custom-30yr.csv
mly-snow-normal-metric-30yr.csv
mly-snow-quantl-custom-30yr.csv
mly-snow-quantl-metric-30yr.csv
mly-snwd-avgnds-custom-30yr.csv
mly-snwd-avgnds-metric-30yr.csv
sea-prcp-normal-custom-30yr.csv
sea-prcp-normal-metric-30yr.csv
sea-snow-normal-custom-30yr.csv
sea-snow-normal-metric-30yr.csv
son-prcp-avgnds-custom-30yr.csv
son-prcp-avgnds-metric-30yr.csv
son-snow-avgnds-custom-30yr.csv
son-snow-avgnds-metric-30yr.csv
son-snwd-avgnds-custom-30yr.csv
son-snwd-avgnds-metric-30yr.csv
----- ann-prcp-avgnds-custom-30yr.csv -----
ANN-PRCP-AVGNDS-GE001HI
ANN-PRCP-AVGNDS-GE010HI
ANN-PRCP-AVGNDS-GE025HI
ANN-PRCP-AVGNDS-GE050HI
ANN-PRCP-AVGNDS-GE100HI
ANN-PRCP-AVGNDS-GE200HI
ANN-PRCP-AVGNDS-GE400HI
ANN-PRCP-AVGNDS-GE600HI
----- ann-prcp-avgnds-metric-30yr.csv -----
ANN-PRCP-AVGNDS-GE001MM
ANN-PRCP-AVGNDS-GE005MM
ANN-PRCP-AVGNDS-GE010MM
ANN-PRCP-AVGNDS-GE050MM
ANN-PRCP-AVGNDS-GE100MM
ANN-PRCP-AVGNDS-GE150MM
----- ann-snow-avgnds-custom-30yr.csv -----
ANN-SNOW-AVGNDS-GE001TI
ANN-SNOW-AVGNDS-GE010TI
ANN-SNOW-AVGNDS-GE020TI
ANN-SNOW-AVGNDS-GE030TI
ANN-SNOW-AVGNDS-GE040TI
ANN-SNOW-AVGNDS-GE050TI
ANN-SNOW-AVGNDS-GE100TI
ANN-SNOW-AVGNDS-GE200TI
----- ann-snow-avgnds-metric-30yr.csv -----
ANN-SNOW-AVGNDS-GE005MM
ANN-SNOW-AVGNDS-GE010MM
ANN-SNOW-AVGNDS-GE025MM
ANN-SNOW-AVGNDS-GE100MM
ANN-SNOW-AVGNDS-GE500MM
----- ann-snwd-avgnds-custom-30yr.csv -----
ANN-SNWD-AVGNDS-GE001WI
ANN-SNWD-AVGNDS-GE002WI
ANN-SNWD-AVGNDS-GE003WI
ANN-SNWD-AVGNDS-GE004WI
ANN-SNWD-AVGNDS-GE005WI
ANN-SNWD-AVGNDS-GE010WI
ANN-SNWD-AVGNDS-GE020WI
----- ann-snwd-avgnds-metric-30yr.csv -----
ANN-SNWD-AVGNDS-GE025MM
ANN-SNWD-AVGNDS-GE100MM
ANN-SNWD-AVGNDS-GE500MM
----- djf-prcp-avgnds-custom-30yr.csv -----
DJF-PRCP-AVGNDS-GE001HI
DJF-PRCP-AVGNDS-GE010HI
DJF-PRCP-AVGNDS-GE025HI
DJF-PRCP-AVGNDS-GE050HI
DJF-PRCP-AVGNDS-GE100HI
DJF-PRCP-AVGNDS-GE200HI
DJF-PRCP-AVGNDS-GE400HI
DJF-PRCP-AVGNDS-GE600HI
----- djf-prcp-avgnds-metric-30yr.csv -----
DJF-PRCP-AVGNDS-GE001MM
DJF-PRCP-AVGNDS-GE005MM
DJF-PRCP-AVGNDS-GE010MM
DJF-PRCP-AVGNDS-GE050MM
DJF-PRCP-AVGNDS-GE100MM
DJF-PRCP-AVGNDS-GE150MM
----- djf-snow-avgnds-custom-30yr.csv -----
DJF-SNOW-AVGNDS-GE001TI
DJF-SNOW-AVGNDS-GE010TI
DJF-SNOW-AVGNDS-GE020TI
DJF-SNOW-AVGNDS-GE030TI
DJF-SNOW-AVGNDS-GE040TI
DJF-SNOW-AVGNDS-GE050TI
DJF-SNOW-AVGNDS-GE100TI
DJF-SNOW-AVGNDS-GE200TI
----- djf-snow-avgnds-metric-30yr.csv -----
DJF-SNOW-AVGNDS-GE005MM
DJF-SNOW-AVGNDS-GE010MM
DJF-SNOW-AVGNDS-GE025MM
DJF-SNOW-AVGNDS-GE100MM
DJF-SNOW-AVGNDS-GE500MM
----- djf-snwd-avgnds-custom-30yr.csv -----
DJF-SNWD-AVGNDS-GE001WI
DJF-SNWD-AVGNDS-GE002WI
DJF-SNWD-AVGNDS-GE003WI
DJF-SNWD-AVGNDS-GE004WI
DJF-SNWD-AVGNDS-GE005WI
DJF-SNWD-AVGNDS-GE010WI
DJF-SNWD-AVGNDS-GE020WI
----- djf-snwd-avgnds-metric-30yr.csv -----
DJF-SNWD-AVGNDS-GE025MM
DJF-SNWD-AVGNDS-GE100MM
DJF-SNWD-AVGNDS-GE500MM
----- jja-prcp-avgnds-custom-30yr.csv -----
JJA-PRCP-AVGNDS-GE001HI
JJA-PRCP-AVGNDS-GE010HI
JJA-PRCP-AVGNDS-GE025HI
JJA-PRCP-AVGNDS-GE050HI
JJA-PRCP-AVGNDS-GE100HI
JJA-PRCP-AVGNDS-GE200HI
JJA-PRCP-AVGNDS-GE400HI
JJA-PRCP-AVGNDS-GE600HI
----- jja-prcp-avgnds-metric-30yr.csv -----
JJA-PRCP-AVGNDS-GE001MM
JJA-PRCP-AVGNDS-GE005MM
JJA-PRCP-AVGNDS-GE010MM
JJA-PRCP-AVGNDS-GE050MM
JJA-PRCP-AVGNDS-GE100MM
JJA-PRCP-AVGNDS-GE150MM
----- jja-snow-avgnds-custom-30yr.csv -----
JJA-SNOW-AVGNDS-GE001TI
JJA-SNOW-AVGNDS-GE010TI
JJA-SNOW-AVGNDS-GE020TI
JJA-SNOW-AVGNDS-GE030TI
JJA-SNOW-AVGNDS-GE040TI
JJA-SNOW-AVGNDS-GE050TI
JJA-SNOW-AVGNDS-GE100TI
JJA-SNOW-AVGNDS-GE200TI
----- jja-snow-avgnds-metric-30yr.csv -----
JJA-SNOW-AVGNDS-GE005MM
JJA-SNOW-AVGNDS-GE010MM
JJA-SNOW-AVGNDS-GE025MM
JJA-SNOW-AVGNDS-GE100MM
JJA-SNOW-AVGNDS-GE500MM
----- jja-snwd-avgnds-custom-30yr.csv -----
JJA-SNWD-AVGNDS-GE001WI
JJA-SNWD-AVGNDS-GE002WI
JJA-SNWD-AVGNDS-GE003WI
JJA-SNWD-AVGNDS-GE004WI
JJA-SNWD-AVGNDS-GE005WI
JJA-SNWD-AVGNDS-GE010WI
JJA-SNWD-AVGNDS-GE020WI
----- jja-snwd-avgnds-metric-30yr.csv -----
JJA-SNWD-AVGNDS-GE025MM
JJA-SNWD-AVGNDS-GE100MM
JJA-SNWD-AVGNDS-GE500MM
----- mam-prcp-avgnds-custom-30yr.csv -----
MAM-PRCP-AVGNDS-GE001HI
MAM-PRCP-AVGNDS-GE010HI
MAM-PRCP-AVGNDS-GE025HI
MAM-PRCP-AVGNDS-GE050HI
MAM-PRCP-AVGNDS-GE100HI
MAM-PRCP-AVGNDS-GE200HI
MAM-PRCP-AVGNDS-GE400HI
MAM-PRCP-AVGNDS-GE600HI
----- mam-prcp-avgnds-metric-30yr.csv -----
MAM-PRCP-AVGNDS-GE001MM
MAM-PRCP-AVGNDS-GE005MM
MAM-PRCP-AVGNDS-GE010MM
MAM-PRCP-AVGNDS-GE050MM
MAM-PRCP-AVGNDS-GE100MM
MAM-PRCP-AVGNDS-GE150MM
----- mam-snow-avgnds-custom-30yr.csv -----
MAM-SNOW-AVGNDS-GE001TI
MAM-SNOW-AVGNDS-GE010TI
MAM-SNOW-AVGNDS-GE020TI
MAM-SNOW-AVGNDS-GE030TI
MAM-SNOW-AVGNDS-GE040TI
MAM-SNOW-AVGNDS-GE050TI
MAM-SNOW-AVGNDS-GE100TI
MAM-SNOW-AVGNDS-GE200TI
----- mam-snow-avgnds-metric-30yr.csv -----
MAM-SNOW-AVGNDS-GE005MM
MAM-SNOW-AVGNDS-GE010MM
MAM-SNOW-AVGNDS-GE025MM
MAM-SNOW-AVGNDS-GE100MM
MAM-SNOW-AVGNDS-GE500MM
----- mam-snwd-avgnds-custom-30yr.csv -----
MAM-SNWD-AVGNDS-GE001WI
MAM-SNWD-AVGNDS-GE002WI
MAM-SNWD-AVGNDS-GE003WI
MAM-SNWD-AVGNDS-GE004WI
MAM-SNWD-AVGNDS-GE005WI
MAM-SNWD-AVGNDS-GE010WI
MAM-SNWD-AVGNDS-GE020WI
----- mam-snwd-avgnds-metric-30yr.csv -----
MAM-SNWD-AVGNDS-GE025MM
MAM-SNWD-AVGNDS-GE100MM
MAM-SNWD-AVGNDS-GE500MM
----- mly-prcp-avgnds-custom-30yr.csv -----
MLY-PRCP-AVGNDS-GE001HI
MLY-PRCP-AVGNDS-GE010HI
MLY-PRCP-AVGNDS-GE025HI
MLY-PRCP-AVGNDS-GE050HI
MLY-PRCP-AVGNDS-GE100HI
MLY-PRCP-AVGNDS-GE200HI
MLY-PRCP-AVGNDS-GE400HI
MLY-PRCP-AVGNDS-GE600HI
----- mly-prcp-avgnds-metric-30yr.csv -----
MLY-PRCP-AVGNDS-GE001MM
MLY-PRCP-AVGNDS-GE005MM
MLY-PRCP-AVGNDS-GE010MM
MLY-PRCP-AVGNDS-GE050MM
MLY-PRCP-AVGNDS-GE100MM
MLY-PRCP-AVGNDS-GE150MM
----- mly-prcp-normal-custom-30yr.csv -----
MLY-PRCP-NORMAL
----- mly-prcp-normal-metric-30yr.csv -----
MLY-PRCP-NORMAL
----- mly-prcp-quantl-custom-30yr.csv -----
MLY-PRCP-QUAR01
MLY-PRCP-QUAR02
MLY-PRCP-QUAR03
MLY-PRCP-QUIN01
MLY-PRCP-QUIN02
MLY-PRCP-QUIN03
MLY-PRCP-QUIN04
MLY-PRCP-TERC01
MLY-PRCP-TERC02
----- mly-prcp-quantl-metric-30yr.csv -----
MLY-PRCP-QUAR01
MLY-PRCP-QUAR02
MLY-PRCP-QUAR03
MLY-PRCP-QUIN01
MLY-PRCP-QUIN02
MLY-PRCP-QUIN03
MLY-PRCP-QUIN04
MLY-PRCP-TERC01
MLY-PRCP-TERC02
----- mly-snow-avgnds-custom-30yr.csv -----
MLY-SNOW-AVGNDS-GE001TI
MLY-SNOW-AVGNDS-GE010TI
MLY-SNOW-AVGNDS-GE020TI
MLY-SNOW-AVGNDS-GE030TI
MLY-SNOW-AVGNDS-GE040TI
MLY-SNOW-AVGNDS-GE050TI
MLY-SNOW-AVGNDS-GE100TI
MLY-SNOW-AVGNDS-GE200TI
----- mly-snow-avgnds-metric-30yr.csv -----
MLY-SNOW-AVGNDS-GE005MM
MLY-SNOW-AVGNDS-GE010MM
MLY-SNOW-AVGNDS-GE025MM
MLY-SNOW-AVGNDS-GE100MM
MLY-SNOW-AVGNDS-GE500MM
----- mly-snow-normal-custom-30yr.csv -----
MLY-SNOW-NORMAL
----- mly-snow-normal-metric-30yr.csv -----
MLY-SNOW-NORMAL
----- mly-snow-quantl-custom-30yr.csv -----
MLY-SNOW-QUAR01
MLY-SNOW-QUAR02
MLY-SNOW-QUAR03
MLY-SNOW-QUIN01
MLY-SNOW-QUIN02
MLY-SNOW-QUIN03
MLY-SNOW-QUIN04
MLY-SNOW-TERC01
MLY-SNOW-TERC02
----- mly-snow-quantl-metric-30yr.csv -----
MLY-SNOW-QUAR01
MLY-SNOW-QUAR02
MLY-SNOW-QUAR03
MLY-SNOW-QUIN01
MLY-SNOW-QUIN02
MLY-SNOW-QUIN03
MLY-SNOW-QUIN04
MLY-SNOW-TERC01
MLY-SNOW-TERC02
----- mly-snwd-avgnds-custom-30yr.csv -----
MLY-SNWD-AVGNDS-GE001WI
MLY-SNWD-AVGNDS-GE002WI
MLY-SNWD-AVGNDS-GE003WI
MLY-SNWD-AVGNDS-GE004WI
MLY-SNWD-AVGNDS-GE005WI
MLY-SNWD-AVGNDS-GE010WI
MLY-SNWD-AVGNDS-GE020WI
----- mly-snwd-avgnds-metric-30yr.csv -----
MLY-SNWD-AVGNDS-GE025MM
MLY-SNWD-AVGNDS-GE100MM
MLY-SNWD-AVGNDS-GE500MM
----- sea-prcp-normal-custom-30yr.csv -----
ANN-PRCP-NORMAL
MAM-PRCP-NORMAL
JJA-PRCP-NORMAL
SON-PRCP-NORMAL
DJF-PRCP-NORMAL
----- sea-prcp-normal-metric-30yr.csv -----
ANN-PRCP-NORMAL
MAM-PRCP-NORMAL
JJA-PRCP-NORMAL
SON-PRCP-NORMAL
DJF-PRCP-NORMAL
----- sea-snow-normal-custom-30yr.csv -----
ANN-SNOW-NORMAL
MAM-SNOW-NORMAL
JJA-SNOW-NORMAL
SON-SNOW-NORMAL
DJF-SNOW-NORMAL
----- sea-snow-normal-metric-30yr.csv -----
ANN-SNOW-NORMAL
MAM-SNOW-NORMAL
JJA-SNOW-NORMAL
SON-SNOW-NORMAL
DJF-SNOW-NORMAL
----- son-prcp-avgnds-custom-30yr.csv -----
SON-PRCP-AVGNDS-GE001HI
SON-PRCP-AVGNDS-GE010HI
SON-PRCP-AVGNDS-GE025HI
SON-PRCP-AVGNDS-GE050HI
SON-PRCP-AVGNDS-GE100HI
SON-PRCP-AVGNDS-GE200HI
SON-PRCP-AVGNDS-GE400HI
SON-PRCP-AVGNDS-GE600HI
----- son-prcp-avgnds-metric-30yr.csv -----
SON-PRCP-AVGNDS-GE001MM
SON-PRCP-AVGNDS-GE005MM
SON-PRCP-AVGNDS-GE010MM
SON-PRCP-AVGNDS-GE050MM
SON-PRCP-AVGNDS-GE100MM
SON-PRCP-AVGNDS-GE150MM
----- son-snow-avgnds-custom-30yr.csv -----
SON-SNOW-AVGNDS-GE001TI
SON-SNOW-AVGNDS-GE010TI
SON-SNOW-AVGNDS-GE020TI
SON-SNOW-AVGNDS-GE030TI
SON-SNOW-AVGNDS-GE040TI
SON-SNOW-AVGNDS-GE050TI
SON-SNOW-AVGNDS-GE100TI
SON-SNOW-AVGNDS-GE200TI
----- son-snow-avgnds-metric-30yr.csv -----
SON-SNOW-AVGNDS-GE005MM
SON-SNOW-AVGNDS-GE010MM
SON-SNOW-AVGNDS-GE025MM
SON-SNOW-AVGNDS-GE100MM
SON-SNOW-AVGNDS-GE500MM
----- son-snwd-avgnds-custom-30yr.csv -----
SON-SNWD-AVGNDS-GE001WI
SON-SNWD-AVGNDS-GE002WI
SON-SNWD-AVGNDS-GE003WI
SON-SNWD-AVGNDS-GE004WI
SON-SNWD-AVGNDS-GE005WI
SON-SNWD-AVGNDS-GE010WI
SON-SNWD-AVGNDS-GE020WI
----- son-snwd-avgnds-metric-30yr.csv -----
SON-SNWD-AVGNDS-GE025MM
SON-SNWD-AVGNDS-GE100MM
SON-SNWD-AVGNDS-GE500MM
=================================
us-climate-normals_1991-2020_daily_precipitation_by-variable_c20210412.tar.gz
=================================
dly-prcp-pctall-custom-30yr.csv
dly-prcp-pctall-metric-30yr.csv
dly-prcp-quantl-custom-30yr.csv
dly-prcp-quantl-metric-30yr.csv
dly-snow-pctall-custom-30yr.csv
dly-snow-pctall-metric-30yr.csv
dly-snow-quantl-custom-30yr.csv
dly-snow-quantl-metric-30yr.csv
dly-snwd-pctall-custom-30yr.csv
dly-snwd-pctall-metric-30yr.csv
dly-snwd-quantl-custom-30yr.csv
dly-snwd-quantl-metric-30yr.csv
tod-prcp-normal-custom-30yr.csv
tod-prcp-normal-metric-30yr.csv
tod-snow-normal-custom-30yr.csv
tod-snow-normal-metric-30yr.csv
----- dly-prcp-pctall-custom-30yr.csv -----
DLY-PRCP-PCTALL-GE001HI
DLY-PRCP-PCTALL-GE010HI
DLY-PRCP-PCTALL-GE025HI
DLY-PRCP-PCTALL-GE050HI
DLY-PRCP-PCTALL-GE100HI
DLY-PRCP-PCTALL-GE200HI
DLY-PRCP-PCTALL-GE400HI
DLY-PRCP-PCTALL-GE600HI
----- dly-prcp-pctall-metric-30yr.csv -----
DLY-PRCP-PCTALL-GE001MM
DLY-PRCP-PCTALL-GE005MM
DLY-PRCP-PCTALL-GE010MM
DLY-PRCP-PCTALL-GE050MM
DLY-PRCP-PCTALL-GE100MM
DLY-PRCP-PCTALL-GE150MM
----- dly-prcp-quantl-custom-30yr.csv -----
DLY-PRCP-QUAR01
DLY-PRCP-QUAR02
DLY-PRCP-QUAR03
DLY-PRCP-QUIN01
DLY-PRCP-QUIN02
DLY-PRCP-QUIN03
DLY-PRCP-QUIN04
DLY-PRCP-TERC01
DLY-PRCP-TERC02
----- dly-prcp-quantl-metric-30yr.csv -----
DLY-PRCP-QUAR01
DLY-PRCP-QUAR02
DLY-PRCP-QUAR03
DLY-PRCP-QUIN01
DLY-PRCP-QUIN02
DLY-PRCP-QUIN03
DLY-PRCP-QUIN04
DLY-PRCP-TERC01
DLY-PRCP-TERC02
----- dly-snow-pctall-custom-30yr.csv -----
DLY-SNOW-PCTALL-GE001TI
DLY-SNOW-PCTALL-GE010TI
DLY-SNOW-PCTALL-GE020TI
DLY-SNOW-PCTALL-GE030TI
DLY-SNOW-PCTALL-GE040TI
DLY-SNOW-PCTALL-GE050TI
DLY-SNOW-PCTALL-GE100TI
DLY-SNOW-PCTALL-GE200TI
----- dly-snow-pctall-metric-30yr.csv -----
DLY-SNOW-PCTALL-GE005MM
DLY-SNOW-PCTALL-GE010MM
DLY-SNOW-PCTALL-GE025MM
DLY-SNOW-PCTALL-GE100MM
DLY-SNOW-PCTALL-GE500MM
----- dly-snow-quantl-custom-30yr.csv -----
DLY-SNOW-QUAR01
DLY-SNOW-QUAR02
DLY-SNOW-QUAR03
DLY-SNOW-QUIN01
DLY-SNOW-QUIN02
DLY-SNOW-QUIN03
DLY-SNOW-QUIN04
DLY-SNOW-TERC01
DLY-SNOW-TERC02
----- dly-snow-quantl-metric-30yr.csv -----
DLY-SNOW-QUAR01
DLY-SNOW-QUAR02
DLY-SNOW-QUAR03
DLY-SNOW-QUIN01
DLY-SNOW-QUIN02
DLY-SNOW-QUIN03
DLY-SNOW-QUIN04
DLY-SNOW-TERC01
DLY-SNOW-TERC02
----- dly-snwd-pctall-custom-30yr.csv -----
DLY-SNWD-PCTALL-GE001WI
DLY-SNWD-PCTALL-GE002WI
DLY-SNWD-PCTALL-GE003WI
DLY-SNWD-PCTALL-GE004WI
DLY-SNWD-PCTALL-GE005WI
DLY-SNWD-PCTALL-GE010WI
DLY-SNWD-PCTALL-GE020WI
----- dly-snwd-pctall-metric-30yr.csv -----
DLY-SNWD-PCTALL-GE025MM
DLY-SNWD-PCTALL-GE100MM
DLY-SNWD-PCTALL-GE500MM
----- dly-snwd-quantl-custom-30yr.csv -----
DLY-SNWD-QUAR01
DLY-SNWD-QUAR02
DLY-SNWD-QUAR03
DLY-SNWD-QUIN01
DLY-SNWD-QUIN02
DLY-SNWD-QUIN03
DLY-SNWD-QUIN04
DLY-SNWD-TERC01
DLY-SNWD-TERC02
----- dly-snwd-quantl-metric-30yr.csv -----
DLY-SNWD-QUAR01
DLY-SNWD-QUAR02
DLY-SNWD-QUAR03
DLY-SNWD-QUIN01
DLY-SNWD-QUIN02
DLY-SNWD-QUIN03
DLY-SNWD-QUIN04
DLY-SNWD-TERC01
DLY-SNWD-TERC02
----- tod-prcp-normal-custom-30yr.csv -----
MTD-PRCP-NORMAL
YTD-PRCP-NORMAL
----- tod-prcp-normal-metric-30yr.csv -----
MTD-PRCP-NORMAL
YTD-PRCP-NORMAL
----- tod-snow-normal-custom-30yr.csv -----
MTD-SNOW-NORMAL
YTD-SNOW-NORMAL
----- tod-snow-normal-metric-30yr.csv -----
MTD-SNOW-NORMAL
YTD-SNOW-NORMAL
=================================

us-climate-normals_1991-2020_hourly_multivariate_by-variable_c20210420.tar.gz
=================================
hly-clod-percnt.csv
hly-degh-normal.csv
hly-dewp-allall.csv
hly-hidx-normal.csv
hly-pres-allall.csv
hly-temp-allall.csv
hly-wchl-normal.csv
hly-wind-group1.csv
hly-wind-group2.csv
----- hly-clod-percnt.csv -----
HLY-CLOD-PCTCLR
HLY-CLOD-PCTFEW
HLY-CLOD-PCTSCT
HLY-CLOD-PCTBKN
HLY-CLOD-PCTOVC
----- hly-degh-normal.csv -----
HLY-CLDH-NORMAL
HLY-HTDH-NORMAL
----- hly-dewp-allall.csv -----
HLY-DEWP-NORMAL
HLY-DEWP-10PCTL
HLY-DEWP-90PCTL
----- hly-hidx-normal.csv -----
HLY-HIDX-NORMAL
----- hly-pres-allall.csv -----
HLY-PRES-NORMAL
HLY-PRES-10PCTL
HLY-PRES-90PCTL
----- hly-temp-allall.csv -----
HLY-TEMP-NORMAL
HLY-TEMP-10PCTL
HLY-TEMP-90PCTL
----- hly-wchl-normal.csv -----
HLY-WCHL-NORMAL
----- hly-wind-group1.csv -----
HLY-WIND-AVGSPD
HLY-WIND-PCTCLM
HLY-WIND-VCTDIR
HLY-WIND-VCTSPD
----- hly-wind-group2.csv -----
HLY-WIND-1STDIR
HLY-WIND-1STPCT
HLY-WIND-2NDDIR
HLY-WIND-2NDPCT


