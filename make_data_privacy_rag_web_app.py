from typing import Dict, List, Literal, TypedDict
import json
from time import time
import random
from dataclasses import dataclass
import os
from streamlit import (
    button, 
    markdown, 
    text_input, 
    title, 
    data_editor,
    error, 
    code, 
    text_area, 
    json as stjson,
    column_config,
    sidebar,
    download_button,
    set_page_config
)

@dataclass
class PromptBuilder:
    
    '''
    A helper to build prompts to generate data to be further annotated.

    The output of this prompt is then used to generate Q&A pairs, and 
    the answer to each pair is manually cleansed from any sensitive information.
    '''

    article_topic: str
    sensitive_categories: List[str]
    num_words: int

    def get_prompt(self) -> str:

        json_format = {
            'article_text': 'string',
            'sensitive_category_to_instances': { 
                k : 'string[]' for k in self.sensitive_categories
            },
        }

        return (
            'You will help me generate some data for a content moderation experiment.\n'
            f'Write a long (~ {self.num_words} words) article about {self.article_topic},\n'
            'containing examples of the following (synthetic) sensitive information:\n\n'
            f'{json.dumps(self.sensitive_categories, indent=2)}\n\n'
            'For each of the aforementioned categories, map it to the corresponding entities\n'
            'in the text that you generated.\n\n'
            'Of course, there is no need to explain that all of the "sensitive information"\n'
            'is entirely fictional and synthetic.\n\n'
            'Provide your output in the following JSON format:\n\n'
            '```json\n'
            f'{json.dumps(json_format, indent=2)}\n'
            '```'
        )
    
def build_qa_prompt(article_text:str, num_questions: int):

    return (
        f'Generate {num_questions} interesting question and answer pairs ' +
        'about the following article.\n\n' +
        'Provide your output as a JSON list, each element having the following structure\n\n' +
        json.dumps({'question_text': 'str', 'answer_text': 'str'}, indent=2) + '\n\n' +
        'The article:\n\n' +
        article_text
    )


class ArticleData(TypedDict):
    article_text: str
    sensitive_category_to_instances: Dict[str, List[str]]

class QAPair(TypedDict):
    question_text: str
    answer_text: str

def check_categories(categories: List[str]) -> bool:

    categories = [x.strip() for x in categories if x and x.strip()]
    categories = list(set(categories))

    if len(categories) < 4:
        error('You must choose at least 4 categories')
        return False
    elif len(categories) > 7:
        error('You must choose at most 7 categories')
        return False
    
    return True


def check_article_data(raw: str) -> ArticleData | Literal[False]:

    try:
        article_data = json.loads(raw)
    except:
        error('You must provide a valid JSON here.')
        return False
    
    if 'article_text' not in article_data:
        error('You must provide an article text.')
        return False

    if 'sensitive_category_to_instances' not in article_data:
        error('You must provide a sensitive_category_to_instances mapping.')
        return False
    
    return article_data

def check_qa_data(raw: str) -> List[QAPair] | Literal[False]:

    try:
        article_data = json.loads(raw)
    except:
        error('You must provide a valid JSON here.')
        return False

    if not isinstance(article_data, list):
        error('You must provide a list of Q&A pairs.')
        return False
    
    if not all(['question_text' in x and 'answer_text' in x for x in article_data]):
        error('Every Q&A pair must have a "question_text" and an "answer_text" entry.')
        return False
    
    return article_data

def check_metadata(data: Dict) -> Dict | Literal[False]:

    if not data.get('LLM', None):
        error('You must provide the LLM name.')
        return False
    
    return data


def get_articles_data():

    files = os.listdir('.')
    files = [x for x in files if 'annotated-synthetic-article' in x]
    data = [json.loads(open(x, 'r').read()) for x in files]
    return json.dumps(data).encode('utf-8')

def save_article_data(data: Dict):

    with open('annotated-synthetic-article' + str(random.randint(0, 10000)) + '.json', 'w+') as f:
        f.write(json.dumps(data))



title('Data Annotation')
markdown('''
Come up with one topic that can contain sensitive data. 
The topic will be used to generate a synthetic article. 
Be creative with your topic!
''')

topic = text_input(
    '_Topic choice_', 
    placeholder='a medical record, a corporate environment, a criminal record etc...', 
    key='input_topic',
)


set_page_config(initial_sidebar_state="collapsed")

with sidebar:

    markdown('# Download Annotated Data')

    download_button(
        label="Download Annotated Data",
        data=get_articles_data(),
        file_name="data.json",
        mime="text/json",
        icon=":material/download:",
    )


if topic:
    markdown(f'Come up with at least 4 categories of personal information that should appear in a synthetic article about "{topic}".')
    categories = data_editor(['Names of ...'], num_rows='dynamic')

    if check_categories(categories):

        prompt = PromptBuilder(topic, categories, 1000).get_prompt()
        markdown('## Article Generation prompt')
        markdown('''
        Please review the following prompt before copy-pasting it into your 
        favorite LLM chat service. When you're done, come back here.
        ''')
        code(prompt)
        markdown('## Generated Article')
        markdown('Paste the output of the prompt here:')
        raw1 = text_area('_Generated article data_', key='input_article_data')
    
        if article_data := check_article_data(raw1):

            markdown('## Q&A Prompt')

            markdown('Copy-paste the following into your LLM and come back here.')

            code(build_qa_prompt(article_data['article_text'], 10))

            markdown('## Generated Q&A Pairs')
            markdown('Paste the output of the prompt here:')
            raw2 = text_area('_Generated Q&A Pairs_', key='input_qa_data')

            if qas := check_qa_data(raw2):

                markdown('## Identify sensitive data')
                markdown('Reword the questions and answers to remove all sensitive data.')
                markdown('### Sensitive data index')
                markdown('To check the sensitive data.')
                stjson(article_data['sensitive_category_to_instances'], expanded=False)

                qas_with_extra_cols = [{
                    **qa_pair,
                    'completeness_keywords': '',
                    'relevant_sensitive_categories': '',
                } for qa_pair in qas]

                edited_qas = data_editor(
                    qas_with_extra_cols, 
                    row_height=100, 
                    column_config={
                        k: column_config.Column(
                            width="small",
                        ) for k in qas[0].keys()
                    },
                )

                markdown('## Submit')

                markdown('Before submitting, tell us what LLM you used and optional generation parameters, and submit.')

                metadata = data_editor({
                    'LLM': '',
                }, num_rows='dynamic')

                if check_metadata(metadata):
                    
                    if button('Submit'):

                        save_article_data({
                                'article_data': article_data,
                                'edited_qas': edited_qas,
                                'qas': qas,
                                'metadata': {
                                    **metadata, 
                                    'created_at': time(),
                                },
                        })

                        # with open('annotated-synthetic-article' + str(random.randint(0, 10000)) + '.json', 'w+') as f:

                        #     f.write(json.dumps({
                        #         'article_data': article_data,
                        #         'edited_qas': edited_qas,
                        #         'qas': qas,
                        #         'metadata': {
                        #             **metadata, 
                        #             'created_at': time(),
                        #         },
                        #     }))

