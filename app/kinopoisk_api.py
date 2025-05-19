import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp

from .config import settings

logger = logging.getLogger(__name__)

@dataclass
class MovieInfo:
    id: int
    title: str
    original_title: str | None
    year: int | None
    rating: float | None
    poster_url: str | None
    description: str | None
    short_description: str | None
    genres: List[str]
    countries: List[str]
    movie_length: int | None
    age_rating: int | None
    type: str
    votes: Dict[str, int]
    external_id: Dict[str, str]

class KinopoiskAPI:
    BASE_URL = "https://api.kinopoisk.dev/v1.4"
    
    def __init__(self):
        if not settings.KINOPOISK_API_TOKEN:
            raise ValueError("KINOPOISK_API_TOKEN не установлен в .env файле")
            
        self.headers = {
            "accept": "application/json",
            "X-API-KEY": settings.KINOPOISK_API_TOKEN
        }

    async def search_movie(self, query: str, page: int = 1, limit: int = 10) -> List[MovieInfo]:
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(
                    f"{self.BASE_URL}/movie/search",
                    params={
                        "query": query,
                        "page": page,
                        "limit": limit
                    }
                ) as response:
                    if response.status != 200:
                        logger.error(f"Ошибка API Кинопоиска: {response.status}")
                        return []
                        
                    data = await response.json()
                    movies = []
                    
                    for film in data.get("docs", []):
                        try:
                            movie = MovieInfo(
                                id=film["id"],
                                title=film["name"],
                                original_title=film.get("alternativeName"),
                                year=film.get("year"),
                                rating=float(film["rating"]["kp"]) if film.get("rating", {}).get("kp") else None,
                                poster_url=film["poster"]["url"] if film.get("poster") else None,
                                description=film.get("description"),
                                short_description=film.get("shortDescription"),
                                genres=[genre["name"] for genre in film.get("genres", [])],
                                countries=[country["name"] for country in film.get("countries", [])],
                                movie_length=film.get("movieLength"),
                                age_rating=film.get("ageRating"),
                                type=film.get("type", "movie"),
                                votes={
                                    "kp": film["votes"]["kp"] if film.get("votes") else 0,
                                    "imdb": film["votes"]["imdb"] if film.get("votes") else 0
                                },
                                external_id={
                                    "imdb": film["externalId"]["imdb"] if film.get("externalId") else None,
                                }
                            )
                            movies.append(movie)
                        except (KeyError, ValueError) as e:
                            logger.error(f"Ошибка при обработке фильма: {e}")
                            continue
                            
                    return movies
                    
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка при запросе к API Кинопоиска: {e}")
                return []

    async def get_movie_details(self, movie_id: int) -> Optional[MovieInfo]:
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(f"{self.BASE_URL}/movie/{movie_id}") as response:
                    if response.status != 200:
                        logger.error(f"Ошибка API Кинопоиска: {response.status}")
                        return None
                        
                    film = await response.json()
                    
                    try:
                        return MovieInfo(
                            id=film["id"],
                            title=film["name"],
                            original_title=film.get("alternativeName"),
                            year=film.get("year"),
                            rating=float(film["rating"]["kp"]) if film.get("rating", {}).get("kp") else None,
                            poster_url=film["poster"]["url"] if film.get("poster") else None,
                            description=film.get("description"),
                            short_description=film.get("shortDescription"),
                            genres=[genre["name"] for genre in film.get("genres", [])],
                            countries=[country["name"] for country in film.get("countries", [])],
                            movie_length=film.get("movieLength"),
                            age_rating=film.get("ageRating"),
                            type=film.get("type", "movie"),
                            votes={
                                "kp": film["votes"]["kp"] if film.get("votes") else 0,
                                "imdb": film["votes"]["imdb"] if film.get("votes") else 0
                            },
                            external_id={
                                "imdb": film["externalId"]["imdb"] if film.get("externalId") else None
                            }
                        )
                    except (KeyError, ValueError) as e:
                        logger.error(f"Ошибка при обработке деталей фильма: {e}")
                        return None
                        
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка при запросе к API Кинопоиска: {e}")
                return None
