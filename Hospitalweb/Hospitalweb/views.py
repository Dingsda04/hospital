from django.shortcuts import render
from home.models import Hospital, Department, Error
from django.http import JsonResponse
from django.http import HttpResponse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re
import time
import pgeocode

import pandas as pd
from django.db.models import Q

test = True

unwanted_hospital_names = []
searched_departments = []
state = []

def home(req):
    global unwanted_hospital_names, searched_departments, state
    if req.method == 'POST':
        if req.POST['extract'] == 'true':
            Hospital.objects.all().delete()
            Department.objects.all().delete()
            Error.objects.all().delete()
            start_extraction()
            return render(req, 'index.html', {})
    return render(req, 'index.html', {})

sites = {
    'baden_wuerttemberg': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/baden-wuerttemberg',
    'bayern': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/bayern',
    'berlin': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/berlin',
    'brandenburg': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/brandenburg',
    'bremen': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/bremen',
    'hamburg': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/hamburg',
    'hessen': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/hessen',
    'mecklenburg_vorpommern': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/mecklenburg-vorpommern',
    'niedersachsen': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/niedersachsen',
    'nordrhein_westfalen': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/nordrhein-westfalen',
    'rheinland_pfalz': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/rheinland-pfalz',
    'saarland': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/saarland',
    'sachsen': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/sachsen',
    'sachsen_anhalt': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/sachsen-anhalt',
    'schleswig_holstein': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/schleswig-holstein',
    'thueringen': 'https://www.deutsches-krankenhaus-verzeichnis.de/app/suche/bundesland/thueringen'
}

number = 0

count_department = 0

# Hilfsfunktionen

def remove_brackets(text):
    pattern = re.compile(r'\([^()]*\)')
    return pattern.sub('', text).strip()

def get_links(driver, soup):
    ## Get Links
    hospital_links = [a.get('href') for a in soup.select('a') if a.get('href') and a.get('href').startswith('/app/portrait/')]

    iteration = 0
    while len(hospital_links) < int(soup.select('#resultCount')[0].text.strip()):
        print(f'Length: {len(hospital_links)}/{int(soup.select("#resultCount")[0].text.strip())}')
        next_button_script = f'filterPagination({iteration+1},20);return false;'
        driver.execute_script(next_button_script)
        time.sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        additional_links = [a.get('href') for a in soup.select('a') if a.get('href') and a.get('href').startswith('/app/portrait/')]
        hospital_links.extend(additional_links)
        iteration += 1
    else:
        print('Done! Final Length: ', len(hospital_links))


    return hospital_links[:]
        
def extract_plz_ort(text):
    cleaned_text = text.strip()

    match = re.search(r'(\d{5})\s*([^\d]+)', cleaned_text)

    if match:
        plz = match.group(1)
        ort = match.group(2).strip()
        return plz, ort
    else:
        return None, None
    
def bl(n):
    ## Get state by number
    states = {
        1: 'Baden Württemberg', 
        2: 'Bayern',
        3: 'Berlin',
        4: 'Brandenburg', 
        5: 'Bremen',
        6: 'Hamburg',
        7: 'Hessen', 
        8: 'Mecklenburg-Vorpommern',
        9: 'Niedersachsen',
        10: 'Nordrhein-Westfalen',
        11: 'Rheinland-Pfalz',
        12: 'Saarland', 
        13: 'Sachsen',
        14: 'Sachsen-Anhalt',
        15: 'Schleswig-Holstein',
        16: 'Thüringen'
    }
    return states.get(n)

def extract_hospital_name(driver, url):
    driver.get(url)
    driver.implicitly_wait(10)

    html = driver.page_source
    soup = BeautifulSoup(html, 'lxml')

    hospital_name = soup.select_one('h1').text.strip()
    return hospital_name

def extract_tel(div_text):
    tel_match = re.search(r'Tel\.:\s*<a href="tel:(.*?)"', div_text)
    tel = tel_match.group(1) if tel_match else None

    return tel

def extract_mail(div_text):
    mail_match = re.search(r'Mail:\s*<a href="mailto:(.*?)"', div_text)
    mail = mail_match.group(1) if mail_match else None

    return mail

# main

def start_extraction():
    global sites, number, count_department
    print('Starting extraction...')

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--log-level=3")  # Setzen Sie den Log-Level auf 3, um Warnungen zu unterdrücken
    chrome_options.add_argument("--filter-logs=.*TOOLTIP: Option \"content\" provided type \"null\".*")
    chrome_options.add_argument("--filter-logs=.*Google Maps JavaScript API has been loaded directly without loading=async. This can result in suboptimal performance. For best-practice loading patterns please see https://goo.gle/js-api-loading.*") 
    chrome_options.add_argument("--filter-logs=.*For best-practice loading patterns please see https://goo.gle/js-api-loading.*")

    driver = webdriver.Chrome(options=chrome_options)

    hospital_links = []

    for bundesland, URL in sites.items():
        print('Extracting Links from', bundesland, '...')
        driver.get(URL)
        driver.implicitly_wait(2)
        html = driver.page_source
        soup = BeautifulSoup(html, 'lxml')
        hospital_links.extend(get_links(driver, soup))
        
    print('Done with Extracting Links!')

    for hospital_link in hospital_links:
        print('Extracting Data from ', hospital_link, '...')
        number += 1
        print(f'{number}/{len(hospital_links)}')
        hospital_url = f'https://www.deutsches-krankenhaus-verzeichnis.de{hospital_link}'
        hospital_name = extract_hospital_name(driver, hospital_url)

        hospital_id_ = hospital_link.split("/portrait/")[1].split("/start")[0]

        driver.get(hospital_url)
        driver.implicitly_wait(2)

        html = driver.page_source
        soup = BeautifulSoup(html, 'lxml')

        selected_elements = soup.select('div.row p')
        if len(selected_elements) >= 2:
            address = selected_elements[1].text.strip()
        match = re.match(r"([^\d]+)(\d+)([a-zA-Z]*)", address)
        if match:
            strasse = match.group(1).strip()
            hausnummer = match.group(2)
            plz, ort = extract_plz_ort(address)
        else:
            # Store Errors
            print('Error in Line 191')
            continue

        nomi = pgeocode.Nominatim('de')
        result = nomi.query_postal_code(plz)
        try:
            print('Create Hospital...')
            hospital = Hospital.objects.create(
                hospital_id=hospital_id_,
                name=hospital_name,
                street=strasse,
                number=hausnummer,
                state=result['state_name'],
                zipcode=plz,
                city=ort,
                url=hospital_url
            )
        except Exception as e:
                print('Create Error...')
                hospital = Error.objects.create(
                hospital_id=hospital_id_,
                name=hospital_name,
                street=strasse,
                number=hausnummer,
                state=result['state_name'],
                zipcode=plz,
                city=ort,
                url=hospital_url
            )

        try:
            time.sleep(2)
            elements = soup.select('#collapseDepartments .card-body .dashed li a')

        except Exception:
            print('Error in Line 173.')
            continue

        if len(elements) == 0:
            print('Could not find any departments.')
            continue

        for a_tag in elements:
            print('Extracting Data from a_tags...')
            department_name = a_tag.text.strip()
            department_url = a_tag.get('href')

            if department_url.startswith('/app/portrait/') and not department_url.__contains__('personal'):
                department_url_ = f'https://www.deutsches-krankenhaus-verzeichnis.de{department_url}'

                driver.get(department_url_)
                driver.implicitly_wait(2)

                h4_elements = WebDriverWait(driver, 10).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, 'h4[data-da-header="true"]'))
                )
                if len(h4_elements) >= 2:
                    zweites_h4_element = h4_elements[1]

                    parent_element = zweites_h4_element.find_element(By.XPATH, './..')
                    parent_info = parent_element.text
                    parent_info = parent_info.replace("Ärztliche Leitung", "")

                try:
                    tel_link = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, 'a[href^="tel:"]'))
                        )
                except Exception:
                    print('Error in Line 264.')
                    continue

                if tel_link:
                    parent_div = tel_link.find_element(By.XPATH, './..')

                    mail_link = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, 'a[href^="mailto:"]'))
                    )

                    if mail_link:
                        print('Create Department...')
                        department_obj = Department.objects.create(
                            name=remove_brackets(department_name),
                            tel_number=extract_tel(parent_div.get_attribute('innerHTML')),
                            mail=extract_mail(parent_div.get_attribute('innerHTML')),
                            leitung=remove_brackets(str(parent_info)[1:]),
                            url=department_url_
                        )
                        hospital.departments.add(department_obj)
                        Hospital.save(hospital)
                        #Error: each hospital got all departments

def get_results(method, page=1, per_page=100):
    global unwanted_hospital_names, searched_departments, state

    start_index = (page - 1) * per_page
    end_index = start_index + per_page

    if method == 'GET':
        return {}
    elif method == 'POST':
        matching_departments = Department.objects.all()

        if searched_departments != ['all']:
            for keyword in searched_departments:
                matching_departments = matching_departments.filter(name__icontains=keyword)

        hospitals_with_matching_departments = Hospital.objects.filter(departments__in=matching_departments).distinct()
        hospitals_with_matching_departments = hospitals_with_matching_departments.exclude(name__in=unwanted_hospital_names)

        if state != ['all']:
            hospitals_with_matching_departments = hospitals_with_matching_departments.filter(state__in=state)

        hospitals = hospitals_with_matching_departments[start_index:end_index]

    return {
        'hospitals': hospitals,
        'page': page,
        'per_page': per_page,
    }

def remove_spacebar(text):
    return ''.join(','.join(map(str.strip, item.split(','))) for item in text.split(','))

def fetch_data(request):
    if request.method == 'POST':
        departments = request.POST.get('department', 'all').split(',')
        states = request.POST.get('state', 'all').split(',')
        unwanted = request.POST.get('unwanted', '').split(',')

        matching_departments = get_matching_departments(departments)
        hospitals_with_matching_departments = get_filtered_hospitals(matching_departments, states, unwanted)
        
        hospitals = sort_hospitals(hospitals_with_matching_departments, matching_departments)

        return JsonResponse({'hospitals': hospitals})

    return JsonResponse({'error': 'Invalid request method'}, status=400)

def get_matching_departments(departments):
    matching_departments = Department.objects.all()
    if departments != ['all']:
        query = Q()
        for keyword in departments:
            query |= Q(name__icontains=keyword)
        matching_departments = matching_departments.filter(query)
    return matching_departments

def get_filtered_hospitals(matching_departments, states, unwanted):
    hospitals_with_matching_departments = Hospital.objects.filter(departments__in=matching_departments).distinct()
    
    if states != ['all']:
        hospitals_with_matching_departments = hospitals_with_matching_departments.filter(state__in=states)
    
    if unwanted and unwanted != ['']:
        query = Q()
        for name in unwanted:
            name = remove_spacebar(name)
            query |= Q(name__icontains=name)
        hospitals_with_matching_departments = hospitals_with_matching_departments.exclude(query)
        
    return hospitals_with_matching_departments

def sort_hospitals(hospitals_with_matching_departments, matching_departments):
    hospitals = []
    for hospital in hospitals_with_matching_departments:
        hospital_data = {
            'id': hospital.id,
            'name': hospital.name,
            'street': hospital.street,
            'number': hospital.number,
            'zipcode': hospital.zipcode,
            'city': hospital.city,
            'departments': [
                {
                    'id': dept.id,
                    'name': dept.name,
                    'tel_number': dept.tel_number,
                    'mail': dept.mail
                }
                for dept in hospital.departments.all() if dept in matching_departments
            ]
        }
        hospitals.append(hospital_data)
    return hospitals

def export_to_excel(request):
    if request.method == 'POST':
        departments = request.POST.get('department', 'all').split(',')
        states = request.POST.get('state', 'all').split(',')
        unwanted = request.POST.get('unwanted', '').split(',')

        matching_departments = get_matching_departments(departments)
        hospitals_with_matching_departments = get_filtered_hospitals(matching_departments, states, unwanted)
        
        hospitals = sort_hospitals(hospitals_with_matching_departments, matching_departments)

        hospital_data = []
        for hospital in hospitals:
            for department in hospital['departments']:
                hospital_data.append({
                    'Hospital Name': hospital['name'],
                    'Street': hospital['street'],
                    'Number': hospital['number'],
                    'ZIP Code': hospital['zipcode'],
                    'City': hospital['city'],
                    'Department Name': department['name'],
                    'Department Phone': department['tel_number'],
                    'Department Email': department['mail']
                })

        df = pd.DataFrame(hospital_data)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=hospitals.xlsx'
        df.to_excel(response, index=False, engine='openpyxl')

        return response

    return JsonResponse({'error': 'Invalid request method'}, status=400)