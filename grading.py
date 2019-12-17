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

def calculate_total_scores(hw_drops=1):
	def drop_and_calc_sum(row):
		hws = row[[l for l in row.index if re.match("Scaled Homework", l)]].values
		other_scores = row[[l for l in row.index if not re.match("Scaled Homework", l) and l != "Total"]].values
		hws = drop_scores(hws, n=hw_drops)
		return np.sum(np.append(hws, other_scores))
	scores["Total"] = scores.apply(drop_and_calc_sum, axis=1)


def grade(path, config):
	global scores, points_possible, assignment_labels
	scores_raw = pd.read_csv(path)
	scores_raw["SIS User ID"] = scores_raw["SIS User ID"].astype(str)
	assignment_labels = [l for l in scores_raw.columns if re.match(r"(Homework\b|Project\b|OH\b)", l)]
	points_possible = scores_raw.loc[0,assignment_labels]
	scores = scores_raw.loc[1:,][scores_raw["Student"] != "Student, Test"].fillna(0)
	scores = scores.set_index("SIS User ID")[assignment_labels]
	for cat in config:
		try:
			perc_per = config[cat]["percentage"] / (config[cat]["number"] - config[cat]["drops"])
		except ZeroDivisionError:
			perc_per = config[cat]["percentage"]
			calc_category_scores(cat, config[cat]["number"], perc_per)
	calculate_total_scores(hw_drops=config["Homework"]["drops"])


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("-s", "--scores", default="scores.csv", help="Canvas exported scores file")
	parser.add_argument("-c", "--config", default="grading_config.json", help="Grading config")
	parser.add_argument("-o", "--output", default="final_scores.csv", help="Output path")
	params = parser.parse_args()

	with open(params.config) as f:
		config = json.load(f)

	drops = {cat : config[cat]["drops"] if "drops" in config[cat] else 0 for cat in config}
	print(drops)

	grade(params.scores, config)

	scores.to_csv(params.output)
