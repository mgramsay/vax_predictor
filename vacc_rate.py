#! /usr/bin/env python3

import sys
from uk_covid19 import Cov19API
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

# Change predict_from to set when you want the dotted line predictions to start from.
# The date must be in the format YYYY-MM-DD.
# If you select a date that is too early, the script will use the earliest valid date instead.
predict_from = "2021-04-24"
# Change av_period to set the number of days over which to average quantities.
av_period = 14

# ~~~~~ Shouldn't need to change anything below here ~~~~~

# Set the filename to which to write the most recent data
datefmt = "%Y-%m-%d"
today = datetime.today()
day = timedelta(days=1)
filename = "data_{}.csv".format(today.strftime(datefmt))

def read_data(filename):
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

data = read_data(filename)

# Get the latest proportions for plotting as a pie chart
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

# Plot the percentage of adults currently in each category
fig_pie = plt.figure()
ax_pie = fig_pie.gca()
ax_pie.pie(fractions, labels=lbls, autopct="%1.1f%%",startangle=90, counterclock=False)
ax_pie.axis("equal")
fig_pie.savefig("vax_frac.png", format="png")

# How far are we along?
doses_given = fractions[0] + 0.5 * fractions[1]
print("Percentage of doses administered: {:0.1f}%".format(doses_given))

# Calculate the delay between first and second doses
got_ref_date = False
ref_date = data["Date"][0]
for idate, date in enumerate(data["Date"]):
    if data["One"][idate] > data["Two"][-1]:
        ref_date = date
        break
second_dose_delay = (data["Date"][-1] - ref_date).days
# Once the number of people with two doses exceeds the peak in the 1st dose
# data, the above method won't work. To try to manage this, set an upper limit
# of 12 weeks delay (the current maximum recommended gap between doses).
second_dose_delay = min(second_dose_delay, 84)

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

# Copy the historical data into new arrays
predict0 = data["Zero"][0:line+1]
predict1 = data["One"][0:line+1]
predict2 = data["Two"][0:line+1]
predictdose = doses[0:line+1]
# Two possible end dates: when 2nd doses reaches 100%, and when total doses
# reaches 100%. Should be the same, but calculate separately just in case.
detail_end = datetime.strptime("2050-01-01", datefmt).date()
dose_end = datetime.strptime("2050-01-01", datefmt).date()
# Average dose rate at the requested prediction date.
predictrate = (data[">=1"][line] - data[">=1"][line-av_period] + data["Two"][line] - data["Two"][line-av_period])/av_period
# Append predictions onto the copies of the historical data created earlier.
while predict2[-1] < 100.0 or predictdose[-1] < 100.0:
    date += day
    # Index for when the current batch receiving second doses received their
    # first dose
    old = len(predictdate) - second_dose_delay
    if predict0[-1] <= 0.0:
        # If everyone has had their 1st dose (i.e. the zero doses group is
        # empty), assume all of the capacity is used to give 2nd doses. Not
        # sure how realistic this is. I suspect vaccination roll out will
        # slow down towards the end, but I can't predict how that will look.
        delta2 = predictrate
        delta0 = 0.0
    else:
        # Otherwise, assume everyone how received their 1st dose "old" days ago
        # receives their 2nd dose today. Assume any remaining capacity is used
        # to administer 1st doses.
        delta2 = min(predict0[old-1] - predict0[old], predictrate)
        delta0 = min(-(predictrate - delta2), 0.0)
    # Change in 1st dose group = Receiving 1st dose - Receiving 2nd dose
    delta1 = -(delta2 + delta0)
    # How many are now in each group.
    # Set limits to prevent going negative or exceeding 100%.
    new0 = min(max(predict0[-1] + delta0, 0.0), 100.0)
    new1 = min(max(predict1[-1] + delta1, 0.0), 100.0)
    new2 = min(max(predict2[-1] + delta2, 0.0), 100.0)
    # How many doses in total have been administered?
    newdose = min(max(predictdose[-1] + 0.5 * predictrate, 0.0), 100.0)
    # Append the new values to the relevant arrays
    predictdate = np.append(predictdate, date)
    predict0 = np.append(predict0, new0)
    predict1 = np.append(predict1, new1)
    predict2 = np.append(predict2, new2)
    predictdose = np.append(predictdose, newdose)
    # If we've reached 100% updated our predicted end date(s).
    if predict2[-1] >= 100.0:
        detail_end = min(detail_end, date)
    if predictdose[-1] >= 100.0:
        dose_end = min(dose_end, date)

# Now predict how long it will take to reach 100% based on all available data.
# This is purely for comparison. The proper prediction, with a break down of
# the number in each group will be done later.
currentrate = (data[">=1"][-1] - data[">=1"][-1-av_period] + data["Two"][-1] - data["Two"][-1-av_period])/av_period
revised_end = data["Date"][-1] + day * (1.0 + (100.0 - doses_given) / (0.5 * currentrate))
print("")
print("Based on data up to {}, predicted end date: {}".format(prediction_made, detail_end))
print("Revised estimate based on {} days up to {}: {}".format(av_period, data["Date"][-1], revised_end))

# Now let's make another prediction, using all of the available data.
# This is the same process as before, but the requested date is now the most
# recent date in the data we downloaded. Really ought to move this into a
# dedicated function to avoid the repetition...
date = data["Date"][-1]
revisedate = data["Date"].copy()
revise0 = data["Zero"].copy()
revise1 = data["One"].copy()
revise2 = data["Two"].copy()
revisedose = doses.copy()
detail_end = datetime.strptime("2050-01-01", datefmt).date()
dose_end = datetime.strptime("2050-01-01", datefmt).date()
reviserate = (data[">=1"][-1] - data[">=1"][-1-av_period] + data["Two"][-1] - data["Two"][-1-av_period])/av_period
while revise2[-1] < 100.0 or revisedose[-1] < 100.0:
    date += day
    old = len(revisedate) - second_dose_delay
    if revise0[-1] <= 0.0:
        delta2 = reviserate
        delta0 = 0.0
    else:
        delta2 = min(revise0[old-1] - revise0[old], reviserate)
        delta0 = min(-(reviserate - delta2), 0.0)
    delta1 = -(delta2 + delta0)
    new0 = min(max(revise0[-1] + delta0, 0.0), 100.0)
    new1 = min(max(revise1[-1] + delta1, 0.0), 100.0)
    new2 = min(max(revise2[-1] + delta2, 0.0), 100.0)
    newdose = min(max(revisedose[-1] + 0.5 * reviserate, 0.0), 100.0)
    revisedate = np.append(revisedate, date)
    revise0 = np.append(revise0, new0)
    revise1 = np.append(revise1, new1)
    revise2 = np.append(revise2, new2)
    revisedose = np.append(revisedose, newdose)
    if revise2[-1] >= 100.0:
        detail_end = min(detail_end, date)
    if revisedose[-1] >= 100.0:
        dose_end = min(dose_end, date)

# Generate plots of the data
fig = plt.figure()
ax = fig.gca()
ax.plot(predictdate, predict0, linestyle=":", color="indianred")
ax.plot(predictdate, predict1, linestyle=":", color="royalblue")
ax.plot(predictdate, predict2, linestyle=":", color="grey")
ax.plot(predictdate, predictdose, linestyle=":", color="lightgreen")
ax.plot(revisedate, revise0, linestyle="--", color="indianred")
ax.plot(revisedate, revise1, linestyle="--", color="royalblue")
ax.plot(revisedate, revise2, linestyle="--", color="grey")
ax.plot(revisedate, revisedose, linestyle="--", color="lightgreen")
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
