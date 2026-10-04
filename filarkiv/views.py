from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ArchiveFileForm
from .models import ArchiveFile


def file_list(request):
    query = request.GET.get("q", "").strip()

    files = ArchiveFile.objects.all()
    if query:
        files = files.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(file__icontains=query)
        )

    context = {
        "files": files,
        "query": query,
        "total_count": ArchiveFile.objects.count(),
    }
    return render(request, "filarkiv/filarkiv.html", context)


def upload_file(request):
    if request.method == "POST":
        form = ArchiveFileForm(request.POST, request.FILES)
        if form.is_valid():
            # save(commit=False) still fills in a missing title from the
            # filename; see ArchiveFileForm.save.
            archive_file = form.save(commit=False)
            archive_file.uploaded_by = request.user
            archive_file.save()
            return redirect("filarkiv")
    else:
        form = ArchiveFileForm()
    return render(request, "filarkiv/upload_form.html", {"form": form})


@require_POST
def delete_file(request, pk):
    archive_file = get_object_or_404(ArchiveFile, pk=pk)
    archive_file.file.delete(save=False)
    archive_file.delete()
    return redirect("filarkiv")


def download_file(request, pk):
    archive_file = get_object_or_404(ArchiveFile, pk=pk)
    return FileResponse(
        archive_file.file.open("rb"),
        as_attachment=True,
        filename=archive_file.filename,
    )
