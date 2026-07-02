from dataclasses import dataclass

@dataclass
class S3Config:
    access_key: str = ""
    secret_key: str = ""
    bucket: str = ""
    endpoint_url: str = ""
