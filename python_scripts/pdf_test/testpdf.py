
import os
import csv
import sys 
import re
import urllib
import os



from xhtml2pdf import pisa             # import python module

# Define your data
source_html = open('pdf.html','r+').read()
output_filename = "test_in2.pdf"

# Utility function
def convert_html_to_pdf(source_html, output_filename):
    # open output file for writing (truncated binary)
    result_file = open(output_filename, "w+b")

    # convert HTML to PDF
    pisa_status = pisa.CreatePDF(
            source_html,                # the HTML to convert
            dest=result_file)           # file handle to recieve result

    # close output file
    result_file.close()                 # close output file

    # return False on success and True on errors
    return pisa_status.err



def generate_remittance_pdf(filename=None,booking=None):
    #t = Template(open('templates/paperwork/pdf/remittance.xml').read())
    t = loader.get_template('remittance.xml')
    c = Context({"filename": filename,"booking":booking,})
    rml = t.render(c)
    #django templates are unicode, and so need to be encoded to utf-8
    rml = rml.encode('utf8')

    buf = cStringIO.StringIO()
        
    #create the pdf
    rml2pdf.go(rml, outputFileName=buf)
    buf.reset()
    pdfData = buf.read()

    target_filename = os.path.join(settings.MEDIA_ROOT,'uploads',filename)
    filepath = os.path.join('uploads',filename)
    f = open(target_filename,'r+')
    f.write(pdfData)
    f.close()

    #send the response
    # response = HttpResponse(mimetype='application/pdf')
    # response.write(pdfData)
    # response['Content-Disposition'] = 'attachment; filename=output.pdf'

    return target_filename,filepath



if __name__ == "__main__":
    #generate_remittance_pdf('test.pdf')
    # Main program
    pisa.showLogging()
    convert_html_to_pdf(source_html, output_filename)

    
