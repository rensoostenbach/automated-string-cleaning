import difflib
import pandas as pd


def generate_ngram(unique_vals, n=3):
    """ Generate n-gram representations for each entry in unique_vals, with n=3 by default.
        For example: 'example' -> {'exa', 'xam', 'amp', 'mpl', 'ple'}.

    :param unique_vals: a List of Strings containing unique entries.
    :param n: an Integer representing the length of each gram (default value = 3).
    :return: a List of Sets containing Strings, each represent the n-gram representation of each unique word.
    """
    ngram_vals = []
    for i in range(len(unique_vals)):
        ngram_vals.append(set([unique_vals[i][j:j + n] for j in range(len(unique_vals[i]) - n-1)]))
    return ngram_vals


def compute_most_similar(unique_vals, ngram_vals):
    """ Compute the most similar String pair using a variation of the Jaccard distance in combination with n-gram.
        The Jaccard distance (in our context the n-gram similarity) for n-grams [ngram1, ngram2] is given by:
        intersect(ngram1, ngram2) / union(ngram1, ngram2)

    :param unique_vals: a List of Strings containing unique entries.
    :param ngram_vals: a List of Sets containing Strings, each represent the n-gram representation of each unique word.
    :return: a List containing the two most-similar String entries.
    """
    suspects = []
    for i in range(len(ngram_vals)):
        best_ratio = 0
        best_pair = []
        for j in range(i + 1, len(ngram_vals)):
            # Calculate n-gram similarity:
            pair_intersect = ngram_vals[i].intersection(ngram_vals[j])
            pair_union = ngram_vals[i].union(ngram_vals[j])
            if len(pair_union) != 0:
                ratio = len(pair_intersect) / len(pair_union)
            else:
                ratio = 0

            if ratio >= 0.75 and ratio > best_ratio:
                best_ratio = ratio
                best_pair = [unique_vals[i], unique_vals[j]]
        if best_pair:
            suspects.append(best_pair)
    return suspects


def sort_tuples(df, pair):
    """ Sort the Tuple of most-similar entries based on their frequency.

    :param df: a pandas DataFrame consisting of unique entries and their frequency.
    :param pair: a Tuple of Strings consisting of the two most-similar String entries.
    :return: a Tuple (String, Integer) sorted on the Integer value.
    """
    tup = [
        (pair[0], df.at[pair[0]]),
        (pair[1], df.at[pair[1]])
    ]
    tup.sort(key=lambda x: x[1])
    return tup


def compute_ratio(tup, threshold=0.05):
    """ Compute the ratio of two frequencies.

    :param tup: a Tuple (String, Integer)
    :param threshold: an Integer representing a threshold (default value = 0.05).
    :return: Boolean, True if the ratio is below the threshold, False otherwise.
    """
    return True if tup[0][1] / tup[1][1] < threshold else False


def compute_close_matches(df, suspect):
    """ Compute all close matches of a potential outlier using difflib's get_close_matches.

    :param df: a pandas Series consisting of String entries.
    :param suspect: a String representing the potential outlier.
    :return: a List of Sets containing all String entries that are a close match to suspect.
    """
    df = list(filter(None, df))  # We might have none values in df, so we filter them out
    df = [str(x) for x in df if type(x) != str]  # Sometimes the entries in df aren't strings, but they need to be
    return list(set(difflib.get_close_matches(suspect, df)))


def run(df, datatypes, outliers, names):
    """ Run the outlier handling procedure, where each column could be treated differently based on reported outliers
        and their datatype.

    :param df: a pandas DataFrame representing all columns whose datatype are inferred as a String (feature).
    :param datatypes: a List of Strings each representing the data type of each column in df.
    :param outliers: a List of Lists consisting of Strings, where each List of Strings represents all discovered
                     outliers in that column in the df.
    :param names: a List of Strings representing the string features that can be inferred by the PFSMs.
    :return: a pandas DataFrame with no/reduced number of outliers.
    """
    for i, (col, dt, outlier) in enumerate(zip(df, datatypes, outliers)):
        unique_vals = list(df[col].unique())
        unique_freq = df[col].value_counts()

        # Enforce values to be string because it can cause an error otherwise.
        unique_freq.index.map(str)

        # If all values are seen as an outlier, then something went wrong during ptype inference
        if len(unique_vals) == len(outlier):
            # Switch datatype to string
            df[col] = df[col].astype(str)
            datatypes[i] = 'string'

        # Check the outliers detected by ptype, excluding sentences since these are mostly false negatives
        elif outlier and dt != 'sentence':
            for out in outlier:
                # Consider only the < 2.5% outliers.
                if ((unique_freq.at[out] / len(df) < 0.025 and len(unique_vals) / len(df) < 0.8)
                        or (out in df[col].values and dt not in names and dt != 'string')):
                    # Check for similar entries using difflib
                    close_matches = compute_close_matches(unique_vals, out)

                    # Take the most similar entries
                    ngrams = generate_ngram(close_matches)
                    most_sim = compute_most_similar(close_matches, ngrams)

                    for pair in most_sim:
                        if out in pair:
                            # Sort the matches based on their frequency
                            tup = sort_tuples(unique_freq, pair)
                            if compute_ratio(tup):
                                # Replace outlying value with the most similar value
                                print('>> Outlier found in column "{}". Outlier "{}" replaced by "{}".'
                                      .format(col, tup[0][0], tup[1][0]))
                                df[col] = df[col].replace(tup[0][0], tup[1][0])
                            elif dt not in names and dt != 'string':
                                # Replace outlier with most similar entry for numerical columns
                                print('>> Outlier found in column "{}". Outlier "{}" replaced by "{}".'
                                      .format(col, tup[0][0], tup[1][0]))
                                df[col] = df[col].replace(tup[0][0], tup[1][0])

                    if out in df[col].values and dt not in names and dt != 'string':
                        # If the data type outlier is still there, replace it with a random non-outlier value.
                        replaced = False
                        # Stop the replacement process if there is no replacement to choose from
                        if len(set(df[col].unique()).difference(set(outlier))) == 0:
                            continue
                        else:
                            while not replaced:
                                replacement = df[col].sample(1).iloc[0]
                                if replacement not in outlier:
                                    print('>> Outlier found in column "{}". Outlier "{}" replaced by "{}".'
                                          .format(col, out, replacement))
                                    df[col] = df[col].replace(out, replacement)
                                    replaced = True

        elif not outlier and dt in names and dt != 'sentence':
            # Only consider <2.5% frequency entries as candidates
            infreq_vals = unique_freq[(unique_freq.values / len(df) < 0.025) & (len(unique_vals) / len(df) < 0.8)]
            infreq_vals = pd.Series(infreq_vals.index.values, index=infreq_vals)

            # Take the most similar entries
            for item in infreq_vals:
                # Check for similar entries using difflib
                close_matches = compute_close_matches(unique_vals, item)

                # Take the most similar entries
                ngrams = generate_ngram(close_matches)
                most_sim = compute_most_similar(close_matches, ngrams)

                for pair in most_sim:
                    if item in pair:
                        # Sort the matches based on their frequency
                        tup = sort_tuples(unique_freq, pair)
                        if compute_ratio(tup):
                            # Replace outlying value with the most similar value
                            print('>> Outlier found. Outlier {} replaced by {}.'.format(tup[0][0], tup[1][0]))
                            df[col] = df[col].replace(tup[0][0], tup[1][0])
    return df, datatypes
