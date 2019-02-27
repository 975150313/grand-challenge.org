import logging
import uuid
from datetime import timedelta
from pathlib import Path

from django.contrib.postgres.fields import JSONField
from django.core.files import File
from django.db import models
from django.utils import timezone

from grandchallenge.cases.models import RawImageUploadSession, RawImageFile
from grandchallenge.container_exec.backends.docker import (
    Executor,
    cleanup,
    get_file,
)
from grandchallenge.container_exec.models import (
    ContainerImageModel,
    ContainerExecJobModel,
)
from grandchallenge.core.models import UUIDModel
from grandchallenge.jqfileupload.models import StagedFile
from grandchallenge.jqfileupload.widgets.uploader import StagedAjaxFile

logger = logging.getLogger(__name__)


class MLModel(UUIDModel, ContainerImageModel):
    """
    Models are single machine learning algorithms that are used for a
    particular task. Here, `MLModels` are docker container images that are
    run with the input images extracted on `/input/`, and produce an
    output json file at `/output/results.json` along with image files in
    '/output/images/'.
    """

    pass


class Result(UUIDModel):
    job = models.OneToOneField("Job", null=True, on_delete=models.CASCADE)
    images = models.ManyToManyField(
        to="cases.Image", related_name="mlmodel_results"
    )
    output = JSONField(default=dict)


class MLModelExecutor(Executor):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, results_file=Path("/output/results.json"), **kwargs
        )
        self.output_images_dir = Path("/output/images/")

    def _get_result(self):
        """
        Reads all of the images in /output/ and converts to upload session
        """

        try:
            with cleanup(
                self._client.containers.run(
                    image=self._io_image,
                    volumes={
                        self._output_volume: {"bind": "/output/", "mode": "ro"}
                    },
                    name=f"{self._job_id}-reader",
                    detach=True,
                    tty=True,
                    **self._run_kwargs,
                )
            ) as reader:
                self._copy_output_files(
                    container=reader, base_dir=Path(self.output_images_dir)
                )
        except Exception as exc:
            raise RuntimeError(str(exc))

        return super()._get_result()

    def _copy_output_files(self, *, container, base_dir: Path):
        found_files = container.exec_run(f"find {base_dir} -type f")

        if found_files.exit_code != 0:
            logger.warning(f"Error listing {base_dir}")
            return

        output_files = [
            base_dir / Path(f)
            for f in found_files.output.decode().splitlines()
        ]

        if not output_files:
            logger.warning("Output directory is empty")
            return

        # TODO: This thing should not interact with the database
        result = Result.objects.create(job_id=self._job_id)

        # Create the upload session but do not save it until we have the
        # files
        upload_session = RawImageUploadSession(mlmodel_result=result)

        images = []

        for file in output_files:
            new_uuid = uuid.uuid4()

            django_file = File(get_file(container=container, src=file))

            staged_file = StagedFile(
                csrf="staging_conversion_csrf",
                client_id=self._job_id,
                client_filename=file.name,
                file_id=new_uuid,
                timeout=timezone.now() + timedelta(hours=24),
                start_byte=0,
                end_byte=django_file.size - 1,
                total_size=django_file.size,
            )
            staged_file.file.save(f"{uuid.uuid4()}", django_file)
            staged_file.save()

            staged_ajax_file = StagedAjaxFile(new_uuid)

            images.append(
                RawImageFile(
                    upload_session=upload_session,
                    filename=staged_ajax_file.name,
                    staged_file_id=staged_ajax_file.uuid,
                )
            )

        upload_session.save(skip_processing=True)
        RawImageFile.objects.bulk_create(images)
        upload_session.process_images()


class Job(UUIDModel, ContainerExecJobModel):
    mlmodel = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    image = models.ForeignKey(
        "cases.Image", related_name="mlmodel_jobs", on_delete=models.CASCADE
    )

    @property
    def container(self):
        return self.mlmodel

    @property
    def input_files(self):
        return [i.file for i in self.image.files.all()]

    @property
    def executor_cls(self):
        return MLModelExecutor

    def create_result(self, *, result: dict):
        instance, _ = Result.objects.get_or_create(job_id=self.pk)
        instance.output = result
        instance.save()
