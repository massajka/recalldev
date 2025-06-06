import os
import logging

# Предполагается, что DATABASE_URL и engine импортируются из db.py
# или определены здесь аналогично db.py для согласованности.
# Для простоты этого скрипта, определим DATABASE_URL и создадим временный engine.

from sqlmodel import create_engine

DATABASE_URL = "sqlite:///db.sqlite3" # Убедитесь, что это тот же URL, что и в db.py

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def drop_database():
    db_file = DATABASE_URL.split("///")[-1]
    logger.info(f"Attempting to drop database file: {db_file}")

    # Создаем временный engine только для dispose, если db.py не импортируется легко
    # В идеале, если db.py можно импортировать без побочных эффектов, лучше использовать engine оттуда.
    engine = create_engine(DATABASE_URL) 

    if os.path.exists(db_file):
        logger.info(f"Database file '{db_file}' exists.")
        try:
            logger.info("Disposing existing engine connections (if any) before deleting DB file...")
            engine.dispose() # Попытка закрыть соединения, которые могли бы удерживать файл
            logger.info("Engine connections disposed.")

            os.remove(db_file)
            logger.info(f"Successfully deleted database file: {db_file}")
        except OSError as e:
            logger.error(f"Error deleting database file '{db_file}': {e}")
            if hasattr(e, 'winerror') and e.winerror == 32: # WinError 32: The process cannot access the file because it is being used by another process.
                 logger.error(
                    f"The database file '{db_file}' is likely in use by another process. "
                    f"Please ensure all applications using this database (like your bot or other scripts) are stopped."
                 )
        except Exception as e:
            logger.exception(f"An unexpected error occurred while trying to dispose engine or delete DB file '{db_file}':")
    else:
        logger.info(f"Database file '{db_file}' does not exist. Nothing to drop.")

if __name__ == "__main__":
    logger.info("Executing script to drop the database...")
    drop_database()
    logger.info("Script execution finished.")
