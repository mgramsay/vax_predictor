#! /usr/bin/env python3

import sys
from uk_covid19 import Cov19API
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

today = datetime.today()
day = timedelta(days=1)
filename = "data_{}.csv".format(today.strftime("%Y-%b-%d"))

filters = [
    "areaName=United Kingdom",
    "areaType=overview"
]
structure = {
    "date": "date",
    "cumVaccinationFirstDoseUptakeByPublishDatePercentage": "cumVaccinationFirstDoseUptakeByPublishDatePercentage",
    "cumVaccinationSecondDoseUptakeByPublishDatePercentage": "cumVaccinationSecondDoseUptakeByPublishDatePercentage"
}

predict_from = "2021-03-25"
av_period = 14
datefmt = "%Y-%m-%d"

def read_data(filename):
    try:
        data = pd.read_csv(filename)
    except:
        print("Downloading latest data to {}".format(filename))
        api = Cov19API(filters=filters, structure=structure)
        # Could load the data straight into a pandas dataframe,
        # But we may want to play around with the data, so save it instead.
        api.get_csv(save_as=filename)
        data = pd.read_csv(filename)
    datalen = len(data["date"].values)
    datetype = datetime.strptime(data["date"].values[0], datefmt).date()
    dates = np.zeros(datalen, dtype=type(datetype))
    dd = np.zeros(datalen)
    d0 = np.zeros(datalen)
    d1 = np.zeros(datalen)
    d2 = np.zeros(datalen)
    for ival, val in enumerate(reversed(data["date"].values)):
        dates[ival] = datetime.strptime(val, datefmt).date()
        dd[ival] = data["cumVaccinationFirstDoseUptakeByPublishDatePercentage"].values[-ival-1]
        d2[ival] = data["cumVaccinationSecondDoseUptakeByPublishDatePercentage"].values[-ival-1]
        d1[ival] = dd[ival] - d2[ival]
        d0[ival] = 100.0 - dd[ival]

    return {"Date" : dates,
            "Zero" : d0,
            "One" : d1,
            "Two" : d2,
            ">=1" : dd}

data = read_data(filename)

fractions = [data["Two"][-1], data["One"][-1], data["Zero"][-1]]
lbls = ["Fully vaccinated", "Half-vaccinated", "Unvaccinated"]
print("Vaccination percentages as of {}".format(data["Date"][-1]))
for ival, val in enumerate(fractions):
    print("  {:0.1f}% - {}".format(val, lbls[ival]))

doses = data["Two"].copy()
for ival, val in enumerate(data["One"]):
    doses[ival] += 0.5 * val

fig_pie = plt.figure()
ax_pie = fig_pie.gca()
ax_pie.pie(fractions, labels=lbls, autopct="%1.1f%%",startangle=90, counterclock=False)
ax_pie.axis("equal")
fig_pie.savefig("vax_frac.png", format="png")

doses_given = fractions[0] + 0.5 * fractions[1]
print("Percentage of doses administered: {:0.1f}%".format(doses_given))

got_ref_date = False
ref_date = data["Date"][0]
for idate, date in enumerate(data["Date"]):
    if data["One"][idate] > data["Two"][-1]:
        ref_date = date
        break
second_dose_delay = (data["Date"][-1] - ref_date).days

prediction_made = datetime.strptime(predict_from, datefmt).date()
for idate, date in enumerate(data["Date"]):
    if date == prediction_made:
        line = idate
        break
date = data["Date"][line]
predictdate = data["Date"][0:line+1]
old = len(predictdate) - second_dose_delay
earliest_date = data["Date"][second_dose_delay]
if old <= 0:
    print("Insufficient data to predict from this date.")
    print("Earliest valid date is {}.".format(earliest_date))
    sys.exit()
predict0 = data["Zero"][0:line+1]
predict1 = data["One"][0:line+1]
predict2 = data["Two"][0:line+1]
predictdose = doses[0:line+1]
detail_end = datetime.strptime("2050-01-01", datefmt).date()
dose_end = datetime.strptime("2050-01-01", datefmt).date()
predictrate = (data[">=1"][line] - data[">=1"][line-av_period] + data["Two"][line] - data["Two"][line-av_period])/av_period
while predict2[-1] < 100.0 or predictdose[-1] < 100.0:
    date += day
    old = len(predictdate) - second_dose_delay
    if predict0[-1] <= 0.0:
        delta2 = predictrate
        delta0 = 0.0
    else:
        delta2 = min(predict0[old-1] - predict0[old], predictrate)
        delta0 = min(-(predictrate - delta2), 0.0)
    delta1 = -(delta2 + delta0)
    new0 = min(max(predict0[-1] + delta0, 0.0), 100.0)
    new1 = min(max(predict1[-1] + delta1, 0.0), 100.0)
    new2 = min(max(predict2[-1] + delta2, 0.0), 100.0)
    newdose = min(max(predictdose[-1] + 0.5 * predictrate, 0.0), 100.0)
    predictdate = np.append(predictdate, date)
    predict0 = np.append(predict0, new0)
    predict1 = np.append(predict1, new1)
    predict2 = np.append(predict2, new2)
    predictdose = np.append(predictdose, newdose)
    if predict2[-1] >= 100.0:
        detail_end = min(detail_end, date)
    if predictdose[-1] >= 100.0:
        dose_end = min(dose_end, date)

currentrate = (data[">=1"][-1] - data[">=1"][-1-av_period] + data["Two"][-1] - data["Two"][-1-av_period])/av_period
revised_end = data["Date"][-1] + day * (1.0 + (100.0 - doses_given) / (0.5 * currentrate))
print("")
print("Based on data up to {}, predicted end date: {}".format(prediction_made, detail_end))
print("Revised estimate based on {} days up to {}: {}".format(av_period, data["Date"][-1], revised_end))

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

actual_dates = []
actual_per_day1 = []
actual_per_day2 = []
actual_total = []
predict_pd_dates = []
predict_per_day1 = []
predict_per_day2 = []
predict_total = []
revised_pd_dates = []
revised_per_day1 = []
revised_per_day2 = []
revised_total = []
for idate, date in enumerate(data["Date"]):
    if idate > 6:
        actual_dates.append(date)
        sum1 = (data["Zero"][idate-7] - data["Zero"][idate]) / 7.0
        sum2 = (data["Two"][idate] - data["Two"][idate-7]) / 7.0
        actual_per_day1.append(sum1)
        actual_per_day2.append(sum2)
        actual_total.append(0.5*(sum1+sum2))
for idate, date in enumerate(predictdate):
    if idate > 6:
        predict_pd_dates.append(date)
        sum1 = (predict0[idate-7] - predict0[idate]) / 7.0
        sum2 = (predict2[idate] - predict2[idate-7]) / 7.0
        predict_per_day1.append(sum1)
        predict_per_day2.append(sum2)
        predict_total.append(0.5*(sum1+sum2))
for idate, date in enumerate(revisedate):
    if idate > 6:
        revised_pd_dates.append(date)
        sum1 = (revise0[idate-7] - revise0[idate]) / 7.0
        sum2 = (revise2[idate] - revise2[idate-7]) / 7.0
        revised_per_day1.append(sum1)
        revised_per_day2.append(sum2)
        revised_total.append(0.5*(sum1+sum2))

figpd = plt.figure()
axpd = figpd.gca()
axpd.plot(predict_pd_dates, predict_per_day1, linestyle=":", color="indianred")
axpd.plot(predict_pd_dates, predict_per_day2, linestyle=":", color="royalblue")
axpd.plot(predict_pd_dates, predict_total, linestyle=":", color="grey")
axpd.plot(revised_pd_dates, revised_per_day1, linestyle="--", color="indianred")
axpd.plot(revised_pd_dates, revised_per_day2, linestyle="--", color="royalblue")
axpd.plot(revised_pd_dates, revised_total, linestyle="--", color="grey")
axpd.plot(actual_dates, actual_per_day1, linestyle="-", color="red", label="First doses")
axpd.plot(actual_dates, actual_per_day2, linestyle="-", color="blue", label="Second doses")
axpd.plot(actual_dates, actual_total, linestyle="-", color="black", label="All doses")
axpd.set_xlabel("Time")
axpd.set_ylabel("Percentage doses administered per day (7-day average)")
axpd.grid(True)
figpd.autofmt_xdate()
axpd.legend()
figpd.savefig("vax_per_day.png", dpi=512, format="png")
