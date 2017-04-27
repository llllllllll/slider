import requests


def main(job_id, params):
    print(job_id, params)
    response = requests.get(
        'http://localhost:5000/mse',
        params=params,
    )
    response.raise_for_status()
    return float(response.content)
