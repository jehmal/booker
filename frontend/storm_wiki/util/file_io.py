import os
import re
import json
import base64
import datetime
import pytz
from typing import Dict, Any, Optional, List
from .text_processing import parse


class FileIOHelper:
    @staticmethod
    def get_output_dir():
        output_dir = os.getenv("STREAMLIT_OUTPUT_DIR")
        if not output_dir:
            target_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(target_dir, "DEMO_WORKING_DIR")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    @staticmethod
    def read_structure_to_dict(articles_root_path: str) -> Dict[str, Dict[str, str]]:
        articles_dict = {}
        for topic_name in os.listdir(articles_root_path):
            topic_path = os.path.join(articles_root_path, topic_name)
            if os.path.isdir(topic_path):
                articles_dict[topic_name] = {}
                for file_name in os.listdir(topic_path):
                    file_path = os.path.join(topic_path, file_name)
                    articles_dict[topic_name][file_name] = os.path.abspath(file_path)
        return articles_dict

    @staticmethod
    def read_txt_file(file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def read_json_file(file_path: str) -> Any:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def read_image_as_base64(image_path: str) -> str:
        with open(image_path, "rb") as f:
            data = f.read()
            encoded = base64.b64encode(data)
        data = "data:image/png;base64," + encoded.decode("utf-8")
        return data

    @staticmethod
    def set_file_modification_time(
        file_path: str, modification_time_string: str
    ) -> None:
        california_tz = pytz.timezone("America/Los_Angeles")
        modification_time = datetime.datetime.strptime(
            modification_time_string, "%Y-%m-%d %H:%M:%S"
        )
        modification_time = california_tz.localize(modification_time)
        modification_time_utc = modification_time.astimezone(datetime.timezone.utc)
        modification_timestamp = modification_time_utc.timestamp()
        os.utime(file_path, (modification_timestamp, modification_timestamp))

    @staticmethod
    def get_latest_modification_time(path: str) -> str:
        california_tz = pytz.timezone("America/Los_Angeles")
        latest_mod_time = None

        file_paths = []
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_paths.append(os.path.join(root, file))
        else:
            file_paths = [path]

        for file_path in file_paths:
            modification_timestamp = os.path.getmtime(file_path)
            modification_time_utc = datetime.datetime.utcfromtimestamp(
                modification_timestamp
            )
            modification_time_utc = modification_time_utc.replace(
                tzinfo=datetime.timezone.utc
            )
            modification_time_california = modification_time_utc.astimezone(
                california_tz
            )

            if (
                latest_mod_time is None
                or modification_time_california > latest_mod_time
            ):
                latest_mod_time = modification_time_california

        if latest_mod_time is not None:
            return latest_mod_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return datetime.datetime.now(california_tz).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def assemble_article_data(
        article_file_path_dict: Dict[str, str],
    ) -> Optional[Dict[str, Any]]:
        # import logging

        # logging.info(f"Assembling article data for: {article_file_path_dict}")
        # for key, path in article_file_path_dict.items():
        #     logging.info(f"Checking file: {path}")
        #     if os.path.exists(path):
        #         logging.info(f"File exists: {path}")
        #     else:
        #         logging.warning(f"File does not exist: {path}")

        if not isinstance(article_file_path_dict, dict):
            raise TypeError("article_file_path_dict must be a dictionary")

        article_file = next(
            (f for f in article_file_path_dict.keys() if f.endswith(".md")), None
        )
        if not article_file:
            print("No .md file found in the article_file_path_dict")
            return None

        try:
            # Read the article content
            article_content = FileIOHelper.read_txt_file(
                article_file_path_dict[article_file]
            )

            # Parse the article content
            parsed_article_content = parse(article_content)

            # Remove title lines efficiently using regex
            no_title_content = re.sub(
                r"^#{1,3}[^\n]*\n?", "", parsed_article_content, flags=re.MULTILINE
            )

            # Extract the first 100 characters as short_text
            short_text = no_title_content[:100]

            article_data = {
                "article": parsed_article_content,
                "short_text": short_text,
                "citation": None,
            }

            if "url_to_info.json" in article_file_path_dict:
                with open(
                    article_file_path_dict["url_to_info.json"], "r", encoding="utf-8"
                ) as f:
                    url_info = json.load(f)

                citations = {}
                url_to_info = url_info.get("url_to_info", {})
                for i, (url, info) in enumerate(url_to_info.items(), start=1):
                    # logging.info(f"Processing citation {i}: {url}")
                    snippets = info.get("snippets", [])
                    if not snippets and "snippet" in info:
                        snippets = [info["snippet"]]

                    citation = {
                        "url": url,
                        "title": info.get("title", ""),
                        "description": info.get("description", ""),
                        "snippets": snippets,
                    }
                    citations[i] = citation

                article_data["citations"] = citations
            # Add conversation log if available
            if "conversation_log.json" in article_file_path_dict:
                try:
                    conversation_log = FileIOHelper.read_json_file(
                        article_file_path_dict["conversation_log.json"]
                    )
                    # Map agent numbers to names
                    agent_names = {0: "User", 1: "AI Assistant", 2: "Expert"}
                    for entry in conversation_log:
                        if "agent" in entry and isinstance(entry["agent"], int):
                            entry["agent"] = agent_names.get(
                                entry["agent"], f"Agent {entry['agent']}"
                            )
                    article_data["conversation_log"] = conversation_log
                except json.JSONDecodeError:
                    print("Error decoding conversation_log.json")

            return article_data
        except FileNotFoundError as e:
            print(f"File not found: {e}")
        except IOError as e:
            print(f"IO error occurred: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

    @staticmethod
    def _construct_citation_dict_from_search_result(
        search_results: Dict[str, Any],
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        if search_results is None:
            return None
        citation_dict = {}
        for url, index in search_results["url_to_unified_index"].items():
            citation_dict[index] = {
                "url": url,
                "title": search_results["url_to_info"][url]["title"],
                "snippets": [
                    search_results["url_to_info"][url]["snippet"]
                ],  # Change this line
            }
        return citation_dict

    @staticmethod
    def write_txt_file(file_path, content):
        """
        Writes content to a text file.

        Args:
            file_path (str): The path to the text file to be written.
            content (str): The content to write to the file.
        """
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def write_json_file(file_path, data):
        """
        Writes data to a JSON file.

        Args:
            file_path (str): The path to the JSON file to be written.
            data (dict or list): The data to write to the file.
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def create_directory(directory_path):
        """
        Creates a directory if it doesn't exist.

        Args:
            directory_path (str): The path of the directory to create.
        """
        os.makedirs(directory_path, exist_ok=True)

    @staticmethod
    def delete_file(file_path):
        """
        Deletes a file if it exists.

        Args:
            file_path (str): The path of the file to delete.
        """
        if os.path.exists(file_path):
            os.remove(file_path)

    @staticmethod
    def copy_file(source_path, destination_path):
        """
        Copies a file from source to destination.

        Args:
            source_path (str): The path of the source file.
            destination_path (str): The path where the file should be copied to.
        """
        import shutil

        shutil.copy2(source_path, destination_path)

    @staticmethod
    def move_file(source_path, destination_path):
        """
        Moves a file from source to destination.

        Args:
            source_path (str): The path of the source file.
            destination_path (str): The path where the file should be moved to.
        """
        import shutil

        shutil.move(source_path, destination_path)
