import base64
import json
from dataclasses import dataclass

import httpx
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.serialization import load_pem_public_key


@dataclass
class UserData:
    id: str
    name: str
    login: str
    senhaAlterada: str  # fake bool.
    roles: str
    root: bool
    theme: str


# ? if wants to retrieve more user data, uses this endpoint:
# ? /AOnline/apix/api/rest/alunos/user/{user_data.id}


class InsperCrawler:
    PADDING = PKCS1v15()
    ENCODING = "utf-8"
    user_data: UserData

    def __init__(self) -> None:
        # ! for some reason, pass user-agent on headers get us blocked.
        self.session = httpx.Client(base_url="https://sga.insper.edu.br")
        # set cookies
        self.session.get("/AOnline/auth")

        # get RSA public key
        self._public_key_pem = self.session.get(
            "/AOnline/config-properties/public-key"
        ).content

    def __encrypt_password(self, password: str) -> str:
        public_key = load_pem_public_key(self._public_key_pem)
        # encode password
        encoded_password = password.encode(self.ENCODING)
        # encrypt password
        encrypted_password = public_key.encrypt(encoded_password, self.PADDING)  # type: ignore
        # b64 hash password
        b64_result = base64.b64encode(encrypted_password).decode("utf-8")

        return b64_result

    def __parse_user_data(self, res: httpx.Response):
        user_data_cookie = res.cookies["user-data"]

        user_data_bytes = base64.b64decode(user_data_cookie)
        user_data_str = user_data_bytes.decode(self.ENCODING)

        user_data = json.loads(user_data_str)
        self.user_data = UserData(**user_data)

    def login(self, username: str, password: str) -> None:
        # encrypt password
        password = self.__encrypt_password(password)

        res = self.session.post(
            "/AOnline/auth",
            data={"username": username, "password": password},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        if res.status_code != 200:
            raise Exception("Login failed")

        # get user data
        self.__parse_user_data(res)

    # TODO: implement calendar dates retriever
    # endpoint: https://sga.insper.edu.br/AOnline/apix/api/rest/alunos/pessoa/{user_data.id}/events?codAluno={matricula || codAluno}&end=2025-06-08T00:00:00.000-03:00&page=0&size=1000&start=2025-04-27T00:00:00.000-03:00&timezone=false

    # TODO: implement other user_data retriever to get matricula.
