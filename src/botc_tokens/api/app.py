"""The API App for the botc_tokens service."""
# Standard Library
from time import sleep

# Third Party
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse
from urllib.request import urlopen, Request, HTTPError
from wand.color import Color
from wand.image import Image

# Application Specific
from .. import component_path as default_component_path
from ..__version__ import __version__
from ..helpers.role import Role
from ..helpers.token_components import TokenComponents
from ..helpers.token_creation import create_role_token


app = FastAPI()

# Add CORS headers to allow for cross-origin requests. For now, we'll allow all origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_icon(url: str):
    """Download an icon from a URL and create a wand image from it."""
    # First, check that the URL is valid
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ['http', 'https']:
        raise HTTPException(status_code=400, detail="Icon URL is not valid. Must be an HTTP or HTTPS URL.")
    try:
        image_bits = urlopen(url).read()
    except HTTPError as e:
        if e.code == 429:  # Rate limit
            try:
                sleep(0.5)
                # Some sites block requests without a user agent
                req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                image_bits = urlopen(req).read()
            except HTTPError:
                raise HTTPException(status_code=e.code, detail=f"Unable to download icon: {str(e)}, despite retrying.")
        else:
            raise HTTPException(status_code=e.code, detail=f"Unable to download icon: {str(e)}")
    # Parse the image
    img = Image(blob=image_bits)
    # Remove the extra space around the icon
    img.trim(color=Color('rgba(0,0,0,0)'), fuzz=0)
    return img


@app.get("/")
def show_version():
    """Show the version of the botc_tokens service."""
    return {"botc_tokens": __version__}


@app.put("/token/create/role",
         responses={
             200: {
                 "content": {"image/png": {}},
                 "description": "Return the generated token.",
             }
         },
         )
def create_role(role: Role, diameter: int = 575) -> Response:
    """Generate a role token from info.

    Args:
        role: The role information.
        diameter: The diameter of the token. Default is 575 pixels.
    """
    # The icon entry should be a web location, so first thing to do is go download it
    icon = get_icon(role.icon)

    # Now we can create the token
    components = TokenComponents(default_component_path)
    token = create_role_token(icon, role, components, diameter)
    img_bytes = token.make_blob('png')
    token.close()
    return Response(content=img_bytes, media_type="image/png")
