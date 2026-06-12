""" Authenticated user class
Useful to return certain data like token
or current hub. """
from dataclasses import dataclass, field


@dataclass
class AuthenticatedUser:
    """ Represents an authenticated user with relevant information. """
    id: str | None = None
    name: str | None = None
    email: str | None = None
    token: str | None = None
    authcfg_id: str | None = None
    profile: dict = field(default_factory=dict)

    @classmethod
    def from_user_info(cls, user_info: dict, token: str | None = None, authcfg_id: str | None = None):
        """ Factory method to create an AuthenticatedUser instance from user info dictionary. """
        return cls(
            id=user_info.get("sub") or user_info.get("id"),
            name=user_info.get("name") or user_info.get("preferred_username"),
            email=user_info.get("email"),
            token=token,
            authcfg_id=authcfg_id,
            profile=user_info,
        )
    
    def is_authenticated(self) -> bool:
        """ Check if the user is authenticated based on presence of token. """
        return self.token is not None
