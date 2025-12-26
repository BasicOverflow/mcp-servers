"""Metrics analysis functions using pandas, numpy, scipy."""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import zscore
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from .prometheus_client import query_range, parse_time_range


def prometheus_to_dataframe(result: Dict[str, Any]) -> pd.DataFrame:
    """Convert Prometheus query result to pandas DataFrame."""
    if result.get("status") != "success":
        return pd.DataFrame()
    
    data = result.get("data", {})
    if "result" not in data:
        return pd.DataFrame()
    
    rows = []
    for item in data["result"]:
        metric = item.get("metric", {})
        values = item.get("values", [])
        
        for timestamp, value in values:
            row = metric.copy()
            row["timestamp"] = float(timestamp)
            row["value"] = float(value)
            rows.append(row)
    
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df = df.set_index("timestamp")
    
    return df


def calculate_percentiles(df: pd.DataFrame, percentiles: List[int] = [50, 95, 99]) -> Dict[str, float]:
    """Calculate percentiles for time series data."""
    if df.empty or "value" not in df.columns:
        return {}
    
    results = {}
    for p in percentiles:
        results[f"p{p}"] = float(df["value"].quantile(p / 100.0))
    
    return results


def calculate_statistics(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate basic statistics: mean, median, min, max, std dev."""
    if df.empty or "value" not in df.columns:
        return {}
    
    return {
        "mean": float(df["value"].mean()),
        "median": float(df["value"].median()),
        "min": float(df["value"].min()),
        "max": float(df["value"].max()),
        "std_dev": float(df["value"].std()),
        "count": int(len(df))
    }


def calculate_rate(df: pd.DataFrame, window: str = "5m") -> pd.DataFrame:
    """Calculate rate of change over time."""
    if df.empty or "value" not in df.columns:
        return df
    
    df = df.copy()
    df["rate"] = df["value"].diff() / df.index.to_series().diff().dt.total_seconds()
    return df


def calculate_derivative(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate derivative (rate of change over time)."""
    return calculate_rate(df)


def detect_trends(df: pd.DataFrame, direction: Optional[str] = None) -> Dict[str, Any]:
    """Detect upward/downward trends in time series."""
    if df.empty or "value" not in df.columns:
        return {"trend": "unknown", "direction": None, "slope": 0.0}
    
    if len(df) < 2:
        return {"trend": "insufficient_data", "direction": None, "slope": 0.0}
    
    x = np.arange(len(df))
    y = df["value"].values
    
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    
    direction_result = "up" if slope > 0 else "down" if slope < 0 else "flat"
    
    if direction and direction != "any":
        matches = (direction_result == direction) or (direction == "up" and slope > 0) or (direction == "down" and slope < 0)
    else:
        matches = True
    
    return {
        "trend": "detected" if abs(slope) > std_err else "stable",
        "direction": direction_result,
        "slope": float(slope),
        "r_squared": float(r_value ** 2),
        "p_value": float(p_value),
        "matches_filter": matches
    }


def calculate_moving_average(df: pd.DataFrame, window: str = "7d") -> pd.DataFrame:
    """Calculate moving average to smooth out noise."""
    if df.empty or "value" not in df.columns:
        return df
    
    df = df.copy()
    
    if window.endswith("d"):
        days = int(window[:-1])
        window_size = f"{days * 24}h"
    elif window.endswith("h"):
        window_size = window
    else:
        window_size = window
    
    df["moving_avg"] = df["value"].rolling(window=window_size, min_periods=1).mean()
    return df


def forecast_capacity(df: pd.DataFrame, forecast_period: str = "7d") -> Dict[str, Any]:
    """Forecast future usage based on historical trends."""
    if df.empty or "value" not in df.columns or len(df) < 10:
        return {"forecast": "insufficient_data", "projected_value": None}
    
    try:
        df_resampled = df["value"].resample("1h").mean().ffill()
        
        if len(df_resampled) < 24:
            return {"forecast": "insufficient_data", "projected_value": None}
        
        model = ExponentialSmoothing(df_resampled, trend="add", seasonal=None)
        fitted = model.fit()
        
        if forecast_period.endswith("d"):
            periods = int(forecast_period[:-1]) * 24
        elif forecast_period.endswith("h"):
            periods = int(forecast_period[:-1])
        else:
            periods = 24
        
        forecast = fitted.forecast(periods)
        projected_value = float(forecast.iloc[-1])
        
        return {
            "forecast": "success",
            "projected_value": projected_value,
            "current_value": float(df["value"].iloc[-1]),
            "growth_rate": float((projected_value - df["value"].iloc[-1]) / df["value"].iloc[-1] * 100) if df["value"].iloc[-1] > 0 else 0.0
        }
    except Exception as e:
        return {"forecast": "error", "error": str(e), "projected_value": None}


def detect_anomalies(df: pd.DataFrame, baseline_df: Optional[pd.DataFrame] = None, threshold: float = 2.0) -> Dict[str, Any]:
    """Detect statistical outliers/anomalies."""
    if df.empty or "value" not in df.columns:
        return {"anomalies": [], "anomaly_count": 0}
    
    if baseline_df is not None and not baseline_df.empty:
        baseline_mean = baseline_df["value"].mean()
        baseline_std = baseline_df["value"].std()
    else:
        baseline_mean = df["value"].mean()
        baseline_std = df["value"].std()
    
    if baseline_std == 0:
        return {"anomalies": [], "anomaly_count": 0, "baseline_mean": float(baseline_mean)}
    
    z_scores = np.abs((df["value"] - baseline_mean) / baseline_std)
    anomalies = df[z_scores > threshold]
    
    return {
        "anomalies": [
            {
                "timestamp": str(idx),
                "value": float(row["value"]),
                "z_score": float(z_scores.loc[idx])
            }
            for idx, row in anomalies.iterrows()
        ],
        "anomaly_count": int(len(anomalies)),
        "baseline_mean": float(baseline_mean),
        "baseline_std": float(baseline_std),
        "threshold": threshold
    }


def compare_periods(current_df: pd.DataFrame, compare_df: pd.DataFrame) -> Dict[str, Any]:
    """Compare two time periods (week-over-week, month-over-month)."""
    if current_df.empty or compare_df.empty or "value" not in current_df.columns or "value" not in compare_df.columns:
        return {"comparison": "insufficient_data"}
    
    current_stats = calculate_statistics(current_df)
    compare_stats = calculate_statistics(compare_df)
    
    current_mean = current_stats.get("mean", 0)
    compare_mean = compare_stats.get("mean", 0)
    
    if compare_mean == 0:
        change_pct = 0.0
    else:
        change_pct = ((current_mean - compare_mean) / compare_mean) * 100
    
    return {
        "current_period": current_stats,
        "compare_period": compare_stats,
        "change_percent": float(change_pct),
        "change_absolute": float(current_mean - compare_mean)
    }


def calculate_growth_rate(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate percentage change/growth rate."""
    if df.empty or "value" not in df.columns or len(df) < 2:
        return {"growth_rate": 0.0, "initial_value": None, "final_value": None}
    
    initial = df["value"].iloc[0]
    final = df["value"].iloc[-1]
    
    if initial == 0:
        growth_rate = 0.0
    else:
        growth_rate = ((final - initial) / initial) * 100
    
    return {
        "growth_rate": float(growth_rate),
        "initial_value": float(initial),
        "final_value": float(final)
    }


def find_peak_usage(df: pd.DataFrame) -> Dict[str, Any]:
    """Identify peak times/days."""
    if df.empty or "value" not in df.columns:
        return {"peak_time": None, "peak_value": None}
    
    peak_idx = df["value"].idxmax()
    peak_value = df["value"].loc[peak_idx]
    
    return {
        "peak_time": str(peak_idx),
        "peak_value": float(peak_value),
        "peak_hour": peak_idx.hour if hasattr(peak_idx, "hour") else None,
        "peak_day": peak_idx.strftime("%A") if hasattr(peak_idx, "strftime") else None
    }


def correlate_metrics(df1: pd.DataFrame, df2: pd.DataFrame) -> Dict[str, Any]:
    """Find correlation between two metrics."""
    if df1.empty or df2.empty or "value" not in df1.columns or "value" not in df2.columns:
        return {"correlation": None, "p_value": None}
    
    df1_resampled = df1["value"].resample("1h").mean()
    df2_resampled = df2["value"].resample("1h").mean()
    
    merged = pd.merge(df1_resampled, df2_resampled, left_index=True, right_index=True, how="inner")
    
    if len(merged) < 2:
        return {"correlation": None, "p_value": None}
    
    corr, p_value = stats.pearsonr(merged["value_x"], merged["value_y"])
    
    return {
        "correlation": float(corr),
        "p_value": float(p_value),
        "strength": "strong" if abs(corr) > 0.7 else "moderate" if abs(corr) > 0.3 else "weak"
    }


def compare_series(df_list: List[pd.DataFrame], labels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Side-by-side comparison of multiple metrics."""
    if not df_list:
        return {"comparison": "no_data"}
    
    results = {}
    for i, df in enumerate(df_list):
        if df.empty or "value" not in df.columns:
            continue
        
        label = labels[i] if labels and i < len(labels) else f"series_{i}"
        results[label] = calculate_statistics(df)
    
    return {"comparison": results}


def calculate_ratios(numerator_df: pd.DataFrame, denominator_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate efficiency metrics (ratios)."""
    if numerator_df.empty or denominator_df.empty:
        return pd.DataFrame()
    
    num_resampled = numerator_df["value"].resample("1h").mean()
    den_resampled = denominator_df["value"].resample("1h").mean()
    
    merged = pd.merge(num_resampled, den_resampled, left_index=True, right_index=True, how="inner")
    merged["ratio"] = merged["value_x"] / merged["value_y"].replace(0, np.nan)
    
    return merged[["ratio"]]

