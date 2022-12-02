"""
DEPRECIATED - READ FIRST

The following enabled a more developer-friendly solution to login/authentication with Woolies' API.
However, shortly after discovery & implementation, the login-endpoint was removed/disabled.
Nowadays, Woolies requires that customers login with MFA.

"""
import os
import warnings
from urllib.parse import urljoin

import requests
from pydantic import BaseModel
from rich.console import Console
from rich.prompt import Prompt

session: requests.Session
endpoint = "https://api.woolworthsrewards.com.au/wx/"


def __init():
    if (email := os.getenv('WOOLIES_EMAIL')) is not None and (password := os.getenv('WOOLIES_PASS')):
        auth = Auth.login(email, password)  # TODO implement token refresh
    elif (token := os.getenv('WOOLIES_TOKEN')) is not None:
        warnings.warn("WOOLIES_TOKEN is deprecated, use WOOLIES_[EMAIL|PASS] instead", DeprecationWarning)
        session.headers.update({'Authorization': f"Bearer {token}"})
        return
    else:
        auth = Auth.login_cli()  # TODO implement token refresh
    session.headers.update({'Authorization': f"Bearer {auth.bearer}"})


class Auth(BaseModel):
    bearer: str
    refresh: str
    bearerExpiredInSeconds: int
    refreshExpiredInSeconds: int
    passwordResetRequired: bool

    @classmethod
    def login(cls, email: str, password: str):
        url = urljoin(e, 'v2/security/login/rewards')
        body = {'username': email, 'password': password}  # email/pass
        res = session.post(url=url, json=body)
        return cls.parse_obj(res.json()['data'])

    @classmethod
    def login_cli(cls):
        Console().print('Woolworths Login')
        email = Prompt.ask("Email")
        password = Prompt.ask("Password", password=True)
        return cls.login(email, password)  # TODO retry bad pass

    def refresh_token(self):
        url = urljoin(endpoint, 'v2/security/refreshLogin')
        body = {'refresh_token': self.refresh}
        res = session.post(url=url, json=body)

        _auth = self.parse_obj(res.json()['data'])
        for attr in self.__annotations__.keys():
            setattr(self, attr, getattr(_auth, attr))
        return self
