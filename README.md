# UK Vax Predictor

A (relatively) simple collection of Python to attempt to predict how long the UK Covid-19 vaccine rollout will take, based on the [available data](https://coronavirus.data.gov.uk).

## Requirements
Requires Python 3.7+ with the following modules:
* [numpy](https://numpy.org)
* [matplotlib](https://matplotlib.org)
* [pandas](https://pandas.pydata.org)
* [uk-covid19](https://pypi.org/project/uk-covid19)

## Usage
Simply run the `vacc_rate.py` script.

## Results
The script generates a `png` file containing a plot of the percentage of the estimated UK adult population who are unvaccinated, have received a single dose (half-vaccinated), or have received both doses (fully vaccinated) as a function of time.

Solid lines denote the values to date. The dotted lines show the predictions made using data up to the date set via the `predict_from` variable (currently set to 24th April 2021 - the date the script was first written). A vertical purple dashed line marks this date. Dashed lines mark revised predictions based on the full set of available data. The method used to generate predictions is discussed below.

The script also saves the government data it downloads to save having to re-download it if the user decides to modify and re-run the script.

## Prediction method
The following assumptions are made when generating predictions:
* The rate at which doses are administered is assumed be the average daily rate for the preceding 14 days, and is assumed to remain constant over the predicted period.
* The number of second doses administered is equal to the number of first doses administered N days ago. Here N is the number of days ago that the cumulative number of first doses administered was equal to the current cumulative number of second doses administered.
* Once second doses have been accounted for, all remaining capacity is assumed to be used to administer first doses.

## Known problems
The prediction does not account for drops in vaccination rate due to bank holidays and weekends. The latter is somewhat accounted for by the 14 day averaging. However, bank holidays will introduce errors (for example the inability to account for Easter in the dotted line predictions).

# Acknowledgements
The ability to automate getting the latest vaccination data would not have been possible without the Coronavirus Dashboard API developed and maintained by Public Health England, https://publichealthengland.github.io/coronavirus-dashboard-api-python-sdk/