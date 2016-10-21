"""
This is the data module of expd_analytics.
Functions for modifying pandas dataframes/useful things for Expeditors analytics of PYNET test suite data.
"""

__author__ = 'Jessi Shank <jessica.shank@expeditors.com>'


import socket
from datetime import datetime

import numpy as np

REGEX_PATTERN_GCI = r'[A-Z]\w{5,7}'
REGEX_PATTERN_DB_ID = r'[0-9]{15}'


def get_failed_mask(dataframe):
    """return mask of """
    return (dataframe.case_status == 'failed') | ( dataframe.case_status == 'skipped')


def this_month(df, time_col):
    return df[time_col].map(lambda x: x.month) == datetime.now().month


def this_year(df, time_col):
    return df[time_col].map(lambda x: x.year) == datetime.now().year


def today(df, time_col):
    today = datetime.now()
    return df[time_col].map(lambda x: x.day + x.month + x.year) == today.day + today.month + today.year


def any_day(df, time_col, day):
    return df[time_col].map(lambda x: x.day) == day


def any_month(df, time_col, month):
    return df[time_col].map(lambda x: x.month) == month


def any_year(df, time_col, year):
    return df[time_col].map(lambda x: x.year) == year


def return_in_norm_df(df, col, sigma):
    """given a column of a dataframe, return a mask that is within sigma standard deviations of the mean."""
    return np.abs(df[col] - df[col].mean()) <= (sigma*df[col].std())


def return_in_norm_series(series, sigma):
    """return a mask for pandas series that is within sigma standard deviations of the mean."""
    return np.abs(series - series.mean()) <= (sigma*series.std())


def normalize_series(series):
    """normalize a pandas series to 1"""
    return (series - series.mean()) / (series.max() - series.min())


def measure_by_case_action(dataframe, case_action_value, specific_endpoint=None):
    # case action duration over time.
    if specific_endpoint:
        dataframe = dataframe[dataframe.case_endpoint.str.contains(specific_endpoint)]
    case_action_df = dataframe[dataframe.case_action.str.contains(case_action_value)]
    return case_action_df


def return_guuid_latest(result_df):
    """return group_uuid of latest test run

    Keyword arguments:
    result_df -- TestResult pandas DataFrame to find latest group_uuid of.

    Return:
    Str group_uuid of latest test run
    """
    latest_run = result_df[result_df.case_timestamp == result_df.case_timestamp.max()]
    return latest_run.group_uuid.values[0]


def get_hostname(ip):
    """get resolved host name by IP address"""
    hostname, aliases, ipaddresses = socket.gethostbyaddr(ip)
    return hostname


def create_mean_col_from_unique_vals(dataframe, mean_col, unique_col, include=None):
    """Return a small dataframe from a different one when you want to generate a number from the average of each unique
    value in a different column

    Keyword arguments:
    Dataframe -- pandas dataframe
    mean_col -- column you want to get mean value of (str)
    unique col -- column name that has repeating values. function will mask the dataframe on unique values of
        column, then save the mean of each of those masks (str)
    include -- column to include along with mean and unique values, if those values are unique as well (default None)

    Return:
    dictionary of unique values and the mean of mean_col's values
    """
    mean_col_by_unique_col = {mean_col: [], unique_col: [], 'index': []}
    ind = 0
    if include:
        mean_col_by_unique_col[include] = []
    for unique_val in dataframe[unique_col].unique():
        if include:
            included_value = dataframe[include][dataframe[unique_col] == unique_val].unique()[0]
            mean_col_by_unique_col[include].append(included_value)
        mean_col_by_unique_col[unique_col].append(unique_val)
        mean_val = dataframe[mean_col][dataframe[unique_col] == unique_val].mean()
        mean_col_by_unique_col[mean_col].append(mean_val)
        mean_col_by_unique_col['index'].append(ind)
        ind += 1
    return mean_col_by_unique_col


def return_norm_number_vs_string(dataframe, number_col, sigma):
    normed_df = dataframe[return_in_norm_df(dataframe, number_col, sigma)]
    # normed_df.index = create_uniform_tcks(normed_df.number_col)
    return normed_df


def endpoint_v_duration(dataframe, endpoint):
    # time series analysis of server -- mean of each test run over time.
    server_specific_dframe = dataframe[dataframe.case_endpoint.str.contains(endpoint)]
    guids = server_specific_dframe.group_uuid.unique()
    mean_duration = []
    timestamp = []
    for uid in guids:
        uid_df = dataframe[dataframe.group_uuid == uid]
        mean_duration.append(uid_df.case_duration.mean())
        timestamp.append(uid_df.iloc[0].case_timestamp)
    return mean_duration, timestamp


def return_specific_case_over_time(df, case):
    duration_over_time = df[df.case_id == case].dropna()
    return duration_over_time


def return_longest_case_over_time(df, aggregation):
    """Find the case id with the largest mean duration, then return a dataframe of that case for analysis

    Keyword Arguments:
    df -- pandas Dataframe to find longest mean case duration of
    aggregation -- dictionary to aggregate the groupby frame

    Return:
    Dataframe of highest mean case run time
    """
    # finds the case id with the largest mean duration, then returns a dataframe  of just that case
    # agg dict should maybe be pulled out
    groupby_id = df.groupby('case_id')
    mean_duration_df = groupby_id.agg(aggregation).dropna()
    max_duration = mean_duration_df[(mean_duration_df.case_duration.mean_duration ==
                                                   mean_duration_df.case_duration.mean_duration.max())]
    max_duration_over_time = return_specific_case_over_time(df, max_duration.index.values[0])
    return max_duration_over_time


def prune(df, regex_list):
    """
    Remove items from dataframe based on a regex pattern in the case action

    Keyword Arguments:
    df -- pandas Dataframe to prune
    regex_list -- list of RegEx patterns to remove from dataframe

    Return:
    Pruned dataframe
    """
    for regex_pattern in regex_list:
        df = df[~df.case_action.str.contains(regex_pattern)]
    return df


def remove_totally_failed_tests(df):
    """Remove all test runs that completely failed, as they are likely garbage.
    This takes a while, should only be run on initialization of the dataframe/when appending new dataframes"""
    all_runs = df.group_uuid.unique()
    removed_guuids = []
    for test_run in all_runs:
        overall_status = df[(df.group_uuid == test_run) & ~get_failed_mask(df)]
        if not len(overall_status):
            df = df[df.group_uuid != test_run]
            removed_guuids.append(test_run)
    return df, removed_guuids


def highest_failures_by_groupby_count(groupby_df, count):
    mean_status = groupby_df.numeric_status.mean()
    worst = mean_status.sort_values()[:count]
    return worst


def highest_failures_by_df_stdev(df, groupby_key, sigma=0):
    groupby_df = df.groupby(groupby_key)
    vals = groupby_df.numeric_status.mean()
    normed_vals = vals[~return_in_norm_series(vals, sigma)]
    not_pass_fail_100 = normed_vals[(normed_vals <= 0.95) & (normed_vals != 0)]
    return not_pass_fail_100
