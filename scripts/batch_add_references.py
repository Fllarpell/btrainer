import asyncio
from typing import Dict, Any, List

try:
    from app.db.crud.ai_reference_crud import create_ai_reference
    from app.db.models import AISourceType

    from app.db.session import AsyncSessionLocal
except ImportError as e:
    print(f"ImportError: {e}. Please ensure that this script is run in an environment where all project modules are accessible,")
    print("and that the paths to 'ai_reference_crud', 'models', and 'session' are correct relative to your project root.")
    print("You might need to set PYTHONPATH or run this script as a module if it's part of a larger package.")
    exit(1)

new_sources_data: List[Dict[str, Any]] = [
    # URLs
    {
        "source_type": "url",
        "description": "Карл Роджерс консультирует Глорию - Психологос",
        "url": "https://psychologos.ru/articles/view/karl-rodzhers-konsultiruet-gloriyu",
        "citation_details": None,
        "is_active": True,
    },
    {
        "source_type": "url",
        "description": "МКБ-11: Расстройства настроения (ффективные расстройства)",
        "url": "https://psyandneuro.ru/icd-11/mood-disorders/",
        "citation_details": None,
        "is_active": True,
    },
    {
        "source_type": "url",
        "description": "МКБ-11: Нарушения нейропсихического развития",
        "url": "https://psyandneuro.ru/icd-11/neurodevelopmental-disorders/",
        "citation_details": None,
        "is_active": True,
    },
    {
        "source_type": "url",
        "description": "МКБ-11: Тревожные и связанные со страхом расстройства",
        "url": "https://psyandneuro.ru/icd-11/anxiety-or-fear-related-disorders/",
        "citation_details": None,
        "is_active": True,
    },
    {
        "source_type": "url",
        "description": "МКБ-11: Шизофрения и другие первичные психотические расстройства",
        "url": "https://psyandneuro.ru/icd-11/schizophrenia-or-other-primary-psychotic-disorders/",
        "citation_details": None,
        "is_active": True,
    },
    {
        "source_type": "url",
        "description": "МКБ-11: Обсессивно-компульсивные и связанные с ними расстройства",
        "url": "https://psyandneuro.ru/icd-11/obsessive-compulsive-or-related-disorders/",
        "citation_details": None,
        "is_active": True,
    },
    {
        "source_type": "url",
        "description": "МКБ-11: Расстройства, специфически связанные со стрессом",
        "url": "https://psyandneuro.ru/icd-11/disorders-specifically-associated-with-stress/",
        "citation_details": None,
        "is_active": True,
    },
    {
        "source_type": "url",
        "description": "МКБ-11: Расстройства пищевого поведения",
        "url": "https://psyandneuro.ru/icd-11/feeding-or-eating-disorders/",
        "citation_details": None,
        "is_active": True,
    },
    {
        "source_type": "manual",
        "description": "Биполярные расстройства - MSD Manuals (профессиональная версия)",
        "url": "https://www.msdmanuals.com/ru-ru/professional/нарушения-психики/аффективные-расстройства/биполярные-расстройства#Диагностика_v47623816_ru",
        "citation_details": "Раздел: Диагностика",
        "is_active": True,
    },
    {
        "source_type": "other",
        "description": "Этический кодекс психолога - Российское психологическое общество",
        "url": "https://psyrus.ru/rpo/documentation/ethics.php",
        "citation_details": None,
        "is_active": True,
    },
    # Bibliographic Entries
    {
        "source_type": "book",
        "description": "Научно-обоснованная практика в когнитивно-поведенческой терапии",
        "url": None,
        "citation_details": "Добсон, Д., Добсон, К. – СПб.: Питер, 2021. – 400 с.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Практики осознанности в развитии когнитивной сферы: оценка краткосрочной эффективности программы Mindfulness-Based Cognitive Therapy",
        "url": None,
        "citation_details": "Дьяков, Д. Г., Слонова, А. И. // Консультативная психология и психотерапия. – 2019. – Т. 27. – № 1. – С. 30–47.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Когнитивно-поведенческая терапия. От основ к направлениям. 3-е издание",
        "url": None,
        "citation_details": "Джудит Бек, предисловие Аарона Бека. – СПб.: Питер, 2024.",
        "is_active": True,
    },
    {
        "source_type": "manual",
        "description": "Diagnostic and Statistical Manual of Mental Disorders, Fifth Edition, Text Revision (DSM-5-TR)",
        "url": None,
        "citation_details": "American Psychiatric Association. Washington, DC, American Psychiatric Association, 2022.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Руководство по тренингу навыков при терапии пограничного расстройства личности",
        "url": None,
        "citation_details": "Лайнен, М. – М.: Вильямс, 2018. – 336 с.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Техники когнитивной психотерапии",
        "url": None,
        "citation_details": "Лихи, Р. – СПб.: Питер, 2020. – 656 с.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Диагностика саморегуляции человека",
        "url": None,
        "citation_details": "Моросанова, В. И., Бондаренко, И. Н. – М.: Когито-центр, 2015. – 304 с.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Технологии психической саморегуляции",
        "url": None,
        "citation_details": "Прохоров, А. О. – Х.: Изд-во «Гуманитарный центр», 2021. – 360 с.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Когнитивно-поведенческая терапия в лечении пациентов с мигренью",
        "url": "https://cyberleninka.ru/article/n/kognitivno-povedencheskaya-terapiya-v-lechenii-patsientov-s-migrenyu",
        "citation_details": "Головачева Вероника Александровна, Парфенов Владимир Анатольевич // Неврологический журнал. 2015. №3.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Когнитивно-поведенческая терапия. Практическое пособие для специалистов",
        "url": None,
        "citation_details": "Качай И., Федоренко П. – Litres, 2023.",
        "is_active": True,
    },
    {
        "source_type": "research_paper",
        "description": "Effectiveness of a school-based mindfulness program for transdiagnostic prevention in young adolescents",
        "url": None,
        "citation_details": "Johnson, C. [et al.] // Behaviour Research and Therapy. – 2016. – № 81(12). – P. 1–11.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "The Efficacy of Cognitive Behavioral Therapy: A Review of Meta-Analyses",
        "url": None,
        "citation_details": "Hofmann, S. G. [et al.] // Cognitive Therapy and Research. – 2021. – № 36. – P. 427–440.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Cognitive-behavioral therapy in the schools: bringing research to practice through effective implementation",
        "url": None,
        "citation_details": "Forman, S. G., Barakat, N. M. // Psychology in the School. – 2011. – № 48(3). – P. 83–96.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Process-based CBT: the science and core clinical competencies of cognitive behavioral therapy",
        "url": None,
        "citation_details": "Hayes, S. C., Hofmann, S. G. // Oakland: New Harbinger, 2017. – 464 p.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Когнитивно-поведенческая терапия пограничного расстройства личности",
        "url": None,
        "citation_details": "Линехан М. – Litres, 2015.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Когнитивно-поведенческая терапия в современной психологической практике",
        "url": None,
        "citation_details": "Пономаренко Л. П. // Вісник Одеського національного університету. Серія: Психологія. – 2014. – №. 19, Вип. 2. – С. 253-260.",
        "is_active": True,
    },
    {
        "source_type": "research_paper",
        "description": "X Международный Форум Ассоциации когнитивно-поведенческой психотерапии CBTFORUM: Сборник научных статей",
        "url": None,
        "citation_details": "Санкт-Петербург, 24–26 мая 2024 года. – Санкт-Петербург: Международный институт развития когнитивно-поведенческой терапии, 2024. – 128 с. – ISBN 978-5-605-18990-9. – EDN BGQRXO.",
        "is_active": True,
    },
    {
        "source_type": "research_paper",
        "description": "VII Международный съезд Ассоциации когнитивно-поведенческой психотерапии CBTFORUM: Сборник научных статей",
        "url": None,
        "citation_details": "Санкт-Петербург, 21 мая 2021 года. – Санкт-Петербург: СИНЭЛ, 2021. – 178 с. – ISBN 978-5-6045907-3-7. – EDN WYWWIQ.",
        "is_active": True,
    },
    {
        "source_type": "research_paper",
        "description": "VIII Международный Форум Ассоциации Когнитивно-Поведенческой Психотерапии CBTFORUM: Сборник научных статей",
        "url": None,
        "citation_details": "Санкт-Петербург, 20–22 мая 2022 года. – Санкт-Петербург: ООО \"Издательство \"ЛЕМА\", 2022. – 252 с. – ISBN 978-5-00105-709-3. – EDN TBUWUZ.",
        "is_active": True,
    },
    {
        "source_type": "research_paper",
        "description": "IX Международный Форум Ассоциации Когнитивно-Поведенческой Психотерапии CBTFORUM: сборник научных статей",
        "url": None,
        "citation_details": "Санкт-Петербург, 20–21 мая 2023 года. – Санкт-Петербург: Лема, 2023. – 375 с. – EDN EFMDPV.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Когнитивно-поведенческий подход в психологическом консультировании: учебное пособие",
        "url": None,
        "citation_details": "Савинков, С. Н. – Москва : Юрайт, 2024. – 169 с. – ISBN 978-5-534-20441-4. – EDN BCVPUV.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Приемы когнитивно-поведенческой терапии \"третьей волны\" в профессиональной подготовке психологов",
        "url": None,
        "citation_details": "Бараева, Е. И., Галецкий, А. В., Пылинская, Н. А., Шлыкова, Т. Ю. // Научные труды Республиканского института высшей школы. Исторические и психолого-педагогические науки. – 2022. – № 22-3. – С. 32-40. – EDN XUXPRP.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Лечение хронической мигрени и инсомнии с помощью когнитивно-поведенческой терапии",
        "url": None,
        "citation_details": "Головачева В. А. // Медицинский совет. – 2023. – Т. 17. – №. 3. – С. 68-76.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Когнитивно-поведенческая терапия больных алкоголизмом",
        "url": None,
        "citation_details": "Карачевский А. Б. // Новости медицины и фармации. – 2012. – №. 3. – С. 16-17_m.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "КОГНИТИВНО-ПОВЕДЕНЧЕСКАЯ ТЕРАПИЯ В ЛЕЧЕНИИ ХРОНИЧЕСКОЙ МИГРЕНИ: ОПИСАНИЕ КЛИНИЧЕСКОГО СЛУЧАЯ",
        "url": "https://cyberleninka.ru/article/n/kognitivno-povedencheskaya-terapiya-v-lechenii-hronicheskoy-migreni-opisanie-klinicheskogo-sluchaya",
        "citation_details": "Головачева Вероника Александровна, Головачева А. А., Парфенов В. А., Табеева Г. Р., Романов Д. В., Осипова В. В., Кацарава З. // Неврология, нейропсихиатрия, психосоматика. 2021. №1.",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Когнитивно-поведенческая терапия тревоги. Пошаговая программа",
        "url": None,
        "citation_details": "Кнаус У. Д. – Litres, 2019.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Возможности применения когнитивно-поведенческой терапии в коррекции депрессивных и тревожных нарушений после инсульта",
        "url": None,
        "citation_details": "Захарченко Д. А., Петриков С. С. // Консультативная психология и психотерапия. – 2018. – Т. 26. – №. 1. – С. 95-111.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Cognitive Behavioral Therapy for Insomnia (CBT-I): A Primer",
        "url": None,
        "citation_details": "Walker J., Muench A., Perlis M.L., Vargas I. // Klinicheskaia i spetsial\'naia psikhologiia=Clinical Psychology and Special Education, 2022. Vol. 11, no. 2, pp. 123–137. DOI: 10.17759/cpse.2022110208",
        "is_active": True,
    },
    {
        "source_type": "book", # Chapter in a book
        "description": "Личностные расстройства",
        "url": None,
        "citation_details": "Холмогорова А.Б. // Клиническая психология. Том 2 / Холмогорова А.Б. ред. — М., 2012",
        "is_active": True,
    },
    {
        "source_type": "book",
        "description": "Когнитивно-поведенческая терапия пограничного расстройства личности (2008)",
        "url": None,
        "citation_details": "Лайнен М. — М., 2008",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Когнитивно-поведенческая психотерапия интероцептивного воздействия при лечении синдрома раздраженного кишечника",
        "url": None,
        "citation_details": "Мелёхин А.И. [Электронный ресурс] // Клиническая и специальная психология. 2020. Том 9. № 2. С. 1–33. DOI: 10.17759/cpse.2020090201",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Применение когнитивно-поведенческой психотерапии при лечении синдрома беспокойных ног",
        "url": None,
        "citation_details": "Мелёхин А.И. // Консультативная психология и психотерапия. 2018. Том 26. № 2. С. 53–78. DOI: 10.17759/cpp.2018260204",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Стратегии когнитивно-поведенческой психотерапии в реабилитации полинаркомании",
        "url": None,
        "citation_details": "Мелёхин А.И., Веселкова Ю.В. // Консультативная психология и психотерапия. 2015. Том 23. № 2. С. 93–115. DOI: 10.17759/cpp.2015230206",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Метод Mindfulness как центральное направление \"Третьей волны\" когнитивно-поведенческого подхода",
        "url": None,
        "citation_details": "Дьяков, Д. Г., Слонова, А. И. // Актуальные проблемы гуманитарных и социально-экономических наук. – 2017. – Т. 11, № 7. – С. 160-163. – EDN YJGPHN.",
        "is_active": True,
    },
    {
        "source_type": "research_paper", # Article in conference proceedings
        "description": "Когнитивно- поведенческая терапия как \"золотой стандарт\" психотерапии",
        "url": None,
        "citation_details": "Дьяков, Д. Г., Пономарева, Л. Г., Слонова, А. И. // Когнитивно-поведенческий подход в консультировании и психотерапии : материалы Международной научно-практической конференции, Минск, 05–07 октября 2018 года. – Минск: Учреждение образования «Белорусский государственный педагогический университет имени Максима Танка», 2018. – С. 10-18. – EDN SABXBR.",
        "is_active": True,
    },
    {
        "source_type": "article",
        "description": "Проведение когнитивно-поведенческой терапии с детьми и подростками с тревожными расстройствами",
        "url": None,
        "citation_details": "Патриарка Г.С., Петтит Д.В., Сильверман У.К. [Электронный ресурс] // Клиническая и специальная психология. 2022. Том 11. № 2. С. 108–122. DOI: 10.17759/cpse.2022110207",
        "is_active": True,
    },
]

async def add_sources_to_db():
    
    created_count = 0
    error_count = 0

    session: AsyncSession = AsyncSessionLocal()
    try:
        for source_data_dict in new_sources_data:
            try:
                print(f"Attempting to add: {source_data_dict.get('description', 'N/A')[:70]}...")
                await create_ai_reference(db=session, source_data=source_data_dict)
                await session.commit()
                created_count += 1
                print(f"Successfully added: {source_data_dict.get('description', 'N/A')[:70]}")
            except Exception as e:
                await session.rollback()
                print(f"Error adding source '{source_data_dict.get('description', 'N/A')[:70]}...': {e}")
                error_count += 1
    finally:
        await session.close()
        
    print(f"\n--- Batch Import Summary ---")
    print(f"Successfully added {created_count} new sources.")
    if error_count > 0:
        print(f"Failed to add {error_count} sources.")
    print("----------------------------")

if __name__ == "__main__":
    print("Starting batch script to add AI references...")

    if 'AsyncSessionLocal' not in globals() or not callable(AsyncSessionLocal):
        print("Error: `AsyncSessionLocal` is not correctly imported or defined.")
        print("Please ensure `app.db.session.AsyncSessionLocal` is available and correctly imported.")
    else:
        try:
            asyncio.run(add_sources_to_db())
        except RuntimeError as e:
            if "no running event loop" in str(e) or "cannot be called from a running event loop" in str(e):
                 print("RuntimeError with event loop. If you are running this inside an environment that already has an event loop (e.g. Jupyter),")
                 print("you might need to use `await add_sources_to_db()` directly instead of `asyncio.run()`.")
            else:
                print(f"An unexpected RuntimeError occurred: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during script execution: {e}")

    print("Batch script finished.") 
