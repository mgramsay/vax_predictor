#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2021 Martin Ramsay
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
A relatively basic model to predict how long the UK vaccine rollout will take.
Uses Public Health England's Coronavirus Dashboard API to download the latest
available vaccination data to make predictions.
"""

from uk_covid19 import Cov19API
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

# Change predict_from to set when you want the dotted line predictions to start
# from. The date must be in the format YYYY-MM-DD. If you select a date that is
# too early, the script will use the earliest valid date instead.
predict_from = "2021-04-24"
# Change av_period to set the number of days over which to average the dose rate
av_period = 14

# ~~~~~ Shouldn't need to change anything below here ~~~~~

def read_data(filename):
    # Read and repackage the csv data for processing.
    # If the file doesn't exist, download the latest results from the
    # government website.
    try:
        # If this script has already been run today, use the existing data
        data = pd.read_csv(filename)
    except:
        # Otherwise download the latest data
        print("Downloading latest data to {}".format(filename))
        filters = [
            "areaName=United Kingdom",
            "areaType=overview"
        ]
        structure = {
            "date": "date",
            "cumVaccinationFirstDoseUptakeByPublishDatePercentage": "cumVaccinationFirstDoseUptakeByPublishDatePercentage",
            "cumVaccinationSecondDoseUptakeByPublishDatePercentage": "cumVaccinationSecondDoseUptakeByPublishDatePercentage"
        }
        api = Cov19API(filters=filters, structure=structure)
        # Could load the data straight into a pandas dataframe,
        # But we may want to play around with the data, so save it instead.
        api.get_csv(save_as=filename)
        data = pd.read_csv(filename)

    # Setup some empty arrays
    datalen = len(data["date"].values)
    datetype = datetime.strptime(data["date"].values[0], datefmt).date()
    dates = np.zeros(datalen, dtype=type(datetype))
    dd = np.zeros(datalen)
    d0 = np.zeros(datalen)
    d1 = np.zeros(datalen)
    d2 = np.zeros(datalen)
    # Calculate the proportion which have received one, and only one, dose.
    # Note, the data from the government website is in reverse chronological order.
    for ival, val in enumerate(reversed(data["date"].values)):
        dates[ival] = datetime.strptime(val, datefmt).date()
        # Proportion who have received at least one dose
        dd[ival] = data["cumVaccinationFirstDoseUptakeByPublishDatePercentage"].values[-ival-1]
        # Proportion who have received two doses
        d2[ival] = data["cumVaccinationSecondDoseUptakeByPublishDatePercentage"].values[-ival-1]
        # Proportion who have received exactly one dose
        d1[ival] = dd[ival] - d2[ival]
        # Proportion who have not received any doses
        d0[ival] = 100.0 - dd[ival]

    return {"Date" : dates,
            "Zero" : d0,
            "One" : d1,
            "Two" : d2,
            ">=1" : dd}


def make_prediction(idx, data, doses):
    # Function to predict the percentage of UK adults in each category
    # (no doses, 1 dose, 2 doses) over time
    date = data["Date"][idx]
    # Copy the historical data into new arrays
    if idx == -1:
        datelist = data["Date"].copy()
        doses_0 = data["Zero"].copy()
        doses_1 = data["One"].copy()
        doses_2 = data["Two"].copy()
        doses_all = doses.copy()
    else:
        datelist = data["Date"][0:idx+1].copy()
        doses_0 = data["Zero"][0:idx+1].copy()
        doses_1 = data["One"][0:idx+1].copy()
        doses_2 = data["Two"][0:idx+1].copy()
        doses_all = doses[0:idx+1].copy()
    # Two possible end dates: when 2nd doses reaches 100%, and when total doses
    # reaches 100%. Should be the same, but calculate separately just in case.
    detail_end = datetime.strptime("2050-01-01", datefmt).date()
    dose_end = datetime.strptime("2050-01-01", datefmt).date()
    # Average dose rate at the requested prediction date.
    rate = (data[">=1"][idx] - data[">=1"][idx-av_period] + data["Two"][idx] - data["Two"][idx-av_period])/av_period
    # Append predictions onto the copies of the historical data created earlier.
    while doses_2[-1] < 100.0 or doses_all[-1] < 100.0:
        date += day
        # Index for when the current batch receiving second doses received their
        # first dose
        old = len(datelist) - second_dose_delay
        if doses_0[-1] <= 0.0:
            # If everyone has had their 1st dose (i.e. the zero doses group is
            # empty), assume all of the capacity is used to give 2nd doses. Not
            # sure how realistic this is. I suspect vaccination roll out will
            # slow down towards the end, but I can't predict how that will look.
            delta2 = rate
            delta0 = 0.0
        else:
            # Otherwise, assume everyone how received their 1st dose "old" days ago
            # receives their 2nd dose today. Assume any remaining capacity is used
            # to administer 1st doses.
            delta2 = min(doses_0[old-1] - doses_0[old], rate)
            delta0 = min(-(rate - delta2), 0.0)
        # Change in 1st dose group = Receiving 1st dose - Receiving 2nd dose
        delta1 = -(delta2 + delta0)
        # How many are now in each group.
        # Set limits to prevent going negative or exceeding 100%.
        new0 = min(max(doses_0[-1] + delta0, 0.0), 100.0)
        new1 = min(max(doses_1[-1] + delta1, 0.0), 100.0)
        new2 = min(max(doses_2[-1] + delta2, 0.0), 100.0)
        # How many doses in total have been administered?
        newdose = min(max(doses_all[-1] + 0.5 * rate, 0.0), 100.0)
        # Append the new values to the relevant arrays
        datelist = np.append(datelist, date)
        doses_0 = np.append(doses_0, new0)
        doses_1 = np.append(doses_1, new1)
        doses_2 = np.append(doses_2, new2)
        doses_all = np.append(doses_all, newdose)
        # If we've reached 100% updated our predicted end date(s).
        if doses_2[-1] >= 100.0:
            detail_end = min(detail_end, date)
        if doses_all[-1] >= 100.0:
            dose_end = min(dose_end, date)

    return datelist, doses_0, doses_1, doses_2, doses_all, detail_end


# Set the filename to which to write the most recent data
datefmt = "%Y-%m-%d"
today = datetime.today()
day = timedelta(days=1)
filename = "data_{}.csv".format(today.strftime(datefmt))

# Read the data
data = read_data(filename)

# Get the latest proportions
fractions = [data["Two"][-1], data["One"][-1], data["Zero"][-1]]
lbls = ["Fully vaccinated", "Half-vaccinated", "Unvaccinated"]
print("Vaccination percentages as of {}".format(data["Date"][-1]))
# Print the proportions to stdout
for ival, val in enumerate(fractions):
    print("  {:0.1f}% - {}".format(val, lbls[ival]))

# Calculate percentage of all required doses (first and second) that have been administered
doses = data["Two"].copy()
for ival, val in enumerate(data["One"]):
    doses[ival] += 0.5 * val

# How far are we along?
doses_given = fractions[0] + 0.5 * fractions[1]
print("Percentage of doses administered: {:0.1f}%".format(doses_given))

# Calculate the delay between first and second doses
got_ref_date = False
ref_date = data["Date"][0]
for idate, date in enumerate(data["Date"]):
    if data["One"][idate] > data["Two"][-1]:
        ref_date = date
        got_ref_date = True
        break
second_dose_delay = (data["Date"][-1] - ref_date).days
# Once the number of people with two doses exceeds the peak in the 1st dose
# data, the above method won't work. When that happens, use the delay from
# the last available date that the above method would have worked
# (i.e. whenever the 2nd dose numbers reaches the 1st dose peak)
if not got_ref_date:
    two_dose_date = data["Date"][-1]
    one_dose_peak = max(data["One"])
    for idate, date in enumerate(reversed(data["Date"])):
        two_dose = data["Two"][-idate-1]
        if two_dose < one_dose_peak:
            two_dose_date = date
            break
    second_dose_delay = (two_dose_date - ref_date).days

# Find the requested prediction date in the data.
prediction_made = datetime.strptime(predict_from, datefmt).date()
for idate, date in enumerate(data["Date"]):
    if date == prediction_made:
        line = idate
        break
# Check that there is enough historical data for the requested date.
# If not, start the prediction from the earliest possible date.
date = data["Date"][line]
predictdate = data["Date"][0:line+1]
old = len(predictdate) - second_dose_delay
earliest_date = data["Date"][second_dose_delay]
if old <= 0:
    print("Insufficient data to predict from this date.")
    print("Earliest valid date is {}.".format(earliest_date))
    line = second_dose_delay
    date = data["Date"][line]
    predictdate = data["Date"][0:line+1]
    prediction_made = earliest_date

# Co-ordinates for a line to be used later to mark where the prediction starts
line_x = [data["Date"][line], data["Date"][line]]
line_y = [0.0, 100.0]
predictdate, predict0, predict1, predict2, predictdose, predict_end = make_prediction(line, data, doses)
# Now predict how long it will take to reach 100% based on all available data.
# This is purely for comparison. The proper prediction, with a break down of
# the number in each group will be done later.
currentrate = (data[">=1"][-1] - data[">=1"][-1-av_period] + data["Two"][-1] - data["Two"][-1-av_period])/av_period
revised_end = data["Date"][-1] + day * (1.0 + (100.0 - doses_given) / (0.5 * currentrate))
print("")
print("Based on data up to {}, predicted end date: {}".format(prediction_made, predict_end))
print("Revised estimate based on {} days up to {}: {}".format(av_period, data["Date"][-1], revised_end))

# Now let's make another prediction properly, using all of the available data.
revisedate, revise0, revise1, revise2, revisedose, revised_end = make_prediction(-1, data, doses)

# Generate plots of the data
fig = plt.figure()
ax = fig.gca()

# Draw a line to mark where the first prediction starts
ax.plot(line_x, line_y, linestyle=":", color="purple", linewidth=1)
# Plot the original predictions
ax.plot(predictdate, predict0, linestyle=":", color="indianred")
ax.plot(predictdate, predict1, linestyle=":", color="royalblue")
ax.plot(predictdate, predict2, linestyle=":", color="grey")
ax.plot(predictdate, predictdose, linestyle=":", color="lightgreen")
# Plot the revised predictions
ax.plot(revisedate, revise0, linestyle="--", color="indianred")
ax.plot(revisedate, revise1, linestyle="--", color="royalblue")
ax.plot(revisedate, revise2, linestyle="--", color="grey")
ax.plot(revisedate, revisedose, linestyle="--", color="lightgreen")
# Plot the data so far
ax.plot(data["Date"], data["Zero"], linestyle="-", color="red", label="People unvaccinated")
ax.plot(data["Date"], data["One"], linestyle="-", color="blue", label="People half-vaccinated")
ax.plot(data["Date"], data["Two"], linestyle="-", color="black", label="People fully vaccinated")
ax.plot(data["Date"], doses, linestyle="-", color="green", label="Vaccine doses administered")

ax.set_ylim(0.0, 100.0)
ax.set_xlabel("Time")
ax.set_ylabel("Percentage")
ax.grid(True)
fig.autofmt_xdate()
ax.legend()
fig.savefig("vax_rates.png", dpi=512, format="png")
