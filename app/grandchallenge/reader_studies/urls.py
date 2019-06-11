from django.urls import path

from grandchallenge.cases.forms import upload_raw_files_widget
from grandchallenge.reader_studies.views import (
    ReaderStudyList,
    ReaderStudyCreate,
    ReaderStudyDetail,
    AddImagesToReaderStudy,
)

app_name = "reader-studies"

urlpatterns = [
    path("", ReaderStudyList.as_view(), name="list"),
    path("create/", ReaderStudyCreate.as_view(), name="create"),
    path("<slug>/", ReaderStudyDetail.as_view(), name="detail"),
    path("<slug>/add/", AddImagesToReaderStudy.as_view(), name="add-images"),
    path(
        f"<slug>/add/{upload_raw_files_widget.ajax_target_path}",
        upload_raw_files_widget.handle_ajax,
        name="upload-raw-readerstudy-image-files-ajax",
    ),
]
