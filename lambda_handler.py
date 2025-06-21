from mangum import Mangum
from app.main import app  # o ajusta según tu estructura real

handler = Mangum(app)
