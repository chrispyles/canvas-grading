###############################################
##### Script to Grade Exports from Canvas #####
###############################################

import argparse
import pandas as pd
import numpy as np
import re
import json

def drop_scores(scores, n=1):
	if len(scores) < 8:
		return np.append(scores, np.zeros(7-len(scores)))
	for _ in range(n):
		key = np.argmin(scores)
		scores = np.append(scores[:key], scores[key+1:])
	return scores

def scale_to_percentage(score, possible, scale):
  	return score / possible * scale

def calc_category_scores(category, n, percentage_per):
	points = [points_possible[l] for l in points_possible.index if re.match(category, l)]
	if any([re.match("Scaled {}".format(category), l) for l in scores.columns]):
		return
	elif n == 0:
		label = [l for l in scores.columns if re.match("{}".format(category), l)][0]
		assignment_scores = scores[label]
		scaled_scores = assignment_scores.apply(lambda s: scale_to_percentage(s, points[0], percentage_per))
		scores["Scaled {}".format(category)] = scaled_scores
		scores.drop(label, axis=1, inplace=True)
	else:
		for i in range(1, n+1):
			label = [l for l in scores.columns if re.match("{} {}".format(category, i), l)][0]
			assignment_scores = scores[label]
			scaled_scores = assignment_scores.apply(lambda s: scale_to_percentage(s, points[i-1], percentage_per))
			scores["Scaled {} {}".format(category, i)] = scaled_scores
			scores.drop(label, axis=1, inplace=True)

def drop_and_calc_sum(drops, row):
	all_scores = np.array([])
	for cat in drops:
		assignment_scores = row[[l for l in row.index if re.match("Scaled {}".format(cat), l)]].values
		assignment_scores = drop_scores(assignment_scores, n=drops[cat])
		all_scores = np.append(all_scores, assignment_scores)
	if has_attendance:
		all_scores = np.append(all_scores, row["Scaled Attendance"])
	return np.sum(all_scores)

def grade(path, config):
	global scores, points_possible, assignment_labels

	# load and clean scores
	scores_raw = pd.read_csv(path)

	# matching function
	def matches_any_category(label):
		return any([re.match("\\b{}\\b".format(cat), label) for cat in config.keys()])

	# get all assignment labels and points possible
	assignment_labels = [l for l in scores_raw.columns if matches_any_category(l)]
	points_possible = scores_raw.loc[0,assignment_labels]

	# finish cleaning scores
	scores = scores_raw.loc[1:,][scores_raw["Student"] != "Student, Test"].fillna(0)
	scores["SIS User ID"] = scores["SIS User ID"].astype(int).astype(str)
	scores = scores.set_index("SIS User ID")[assignment_labels]

	# get number of assignments to drop
	drops = {cat : config[cat]["drops"] if "drops" in config[cat] else 0 for cat in config}

	for cat in config:
		try:
			perc_per = config[cat]["percentage"] / (config[cat]["number"] - drops[cat])
		except ZeroDivisionError:
			perc_per = config[cat]["percentage"]
		calc_category_scores(cat, config[cat]["number"], perc_per)
	
	if has_attendance:
		scores = pd.merge(
			scores.reset_index(), 
			attendance, 
			left_on = "SIS User ID", 
			right_on = "student_id", 
			how="outer",
			suffixes = (False, False)	
		)
		scores.drop("student_id", axis=1, inplace=True)
		scores.set_index("SIS User ID", inplace=True)
		scores.rename({"attendance_score":"Scaled Attendance"}, axis=1, inplace=True)

	scores["Total"] = scores.apply(lambda row: drop_and_calc_sum(drops, row), axis=1)
	scores.reset_index(inplace=True)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("-s", "--scores", default="scores.csv", help="Canvas exported scores file")
	parser.add_argument("-c", "--config", default="grading_config.json", help="Grading config")
	parser.add_argument("-o", "--output", default="final_scores.csv", help="Output path")
	parser.add_argument("-a", "--attendance", default="attendance.csv", help="Attendance counts")
	params = parser.parse_args()

	with open(params.config) as f:
		config = json.load(f)

	global attendance, has_attendance
	if "Attendance" in config:
		has_attendance = True
		attendance = pd.read_csv(params.attendance)
		attendance["student_id"] = attendance["student_id"].astype(int).astype(str)
		if "cap" in config["Attendance"] and config["Attendance"]["cap"] != "none":
			cap = config["Attendance"][config["Attendance"]["cap"]]
			attendance["count"] = attendance["count"].apply(lambda v: min(v, cap))
		else:
			cap = None
		attendance["attendance_score"] = attendance["count"].apply(
			lambda s: scale_to_percentage(
				s, 
				cap or config["Attendance"]["required"], 
				config["Attendance"]["percentage"]
			)
		)
		attendance.drop("count", axis=1, inplace=True)
		del config["Attendance"]
	else:
		has_attendance = False

	grade(params.scores, config)

	names = pd.read_csv(params.scores)[["SIS User ID", "Student"]].dropna(subset=["SIS User ID"])
	names["SIS User ID"] = names["SIS User ID"].astype(int).astype(str)
	merged_scores = pd.merge(
		scores,
		names,
		on = "SIS User ID",
		how="outer",
		suffixes = (False, False)
	)
	merged_scores = merged_scores[[merged_scores.columns[-1]] + merged_scores.columns[:-1].tolist()]
	merged_scores.to_csv(params.output, index=False)

if __name__ == "__main__":
	main()
