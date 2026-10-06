from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ArchiveFileEditForm, ArchiveFileForm, FolderForm
from .models import ArchiveFile, Folder, folder_paths
from .thumbnails import make_thumbnail

# Served inline, so lock the response down: no script, no subresources, and
# a sandbox in case a browser renders it as a document anyway (ADR 0015).
INLINE_CSP = "default-src 'none'; sandbox"


def file_list(request):
    query = request.GET.get("q", "").strip()

    files = []
    if query:
        files = list(
            ArchiveFile.objects.select_related("uploaded_by").filter(
                Q(title__icontains=query) | Q(description__icontains=query) | Q(file__icontains=query)
            )
        )
        paths = folder_paths()
        for f in files:
            f.folder_path = paths[f.folder_id]

    context = {
        "folders": Folder.objects.filter(parent=None).order_by("root_key"),
        "files": files,
        "query": query,
        "total_count": ArchiveFile.objects.count(),
    }
    return render(request, "filarkiv/filarkiv.html", context)


def folder_detail(request, pk):
    folder = get_object_or_404(Folder, pk=pk)
    files = list(folder.files.select_related("uploaded_by"))
    is_empty = not files and not folder.children.exists()
    context = {
        "folder": folder,
        "breadcrumbs": folder.ancestors(),
        "children": folder.children.all(),
        "images": [f for f in files if f.is_image],
        "documents": [f for f in files if not f.is_image],
        "is_empty": is_empty,
        "can_delete": not folder.is_root and (is_empty or request.user.is_staff),
    }
    return render(request, "filarkiv/folder_detail.html", context)


def folder_create(request, pk):
    parent = get_object_or_404(Folder, pk=pk)
    form = FolderForm(request.POST or None, parent=parent)
    if request.method == "POST" and form.is_valid():
        folder = form.save(commit=False)
        folder.parent = parent
        folder.save()
        return redirect("filarkiv_folder", pk=folder.pk)
    return render(request, "filarkiv/folder_form.html", {"form": form, "parent": parent})


def folder_rename(request, pk):
    folder = get_object_or_404(Folder, pk=pk)
    if folder.is_root:
        return redirect("filarkiv_folder", pk=folder.pk)
    form = FolderForm(request.POST or None, instance=folder, parent=folder.parent)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("filarkiv_folder", pk=folder.pk)
    return render(request, "filarkiv/folder_form.html", {"form": form, "folder": folder, "parent": folder.parent})


@require_POST
def folder_delete(request, pk):
    folder = get_object_or_404(Folder, pk=pk)
    if folder.is_root:
        return HttpResponseForbidden("Billeder og Filer kan ikke slettes.")

    if folder.is_empty():
        folder.delete()
    elif request.user.is_staff:
        _delete_with_contents(folder)
    else:
        return HttpResponseForbidden("Kun en administrator kan slette en mappe med indhold.")
    return redirect("filarkiv_folder", pk=folder.parent_id)


def _delete_with_contents(folder):
    folders = folder.subtree()
    files = list(ArchiveFile.objects.filter(folder__in=folders))
    with transaction.atomic():
        ArchiveFile.objects.filter(pk__in=[f.pk for f in files]).delete()
        # Children before parents: the parent link is PROTECT.
        for f in reversed(folders):
            f.delete()
        # Only touch the disk once the rows are really gone.
        transaction.on_commit(lambda: [f.delete_stored_files() for f in files])


def upload_file(request):
    if request.method == "POST":
        form = ArchiveFileForm(request.POST, request.FILES)
        if form.is_valid():
            # save(commit=False) still fills in a missing title from the
            # filename; see ArchiveFileForm.save.
            archive_file = form.save(commit=False)
            archive_file.uploaded_by = request.user
            archive_file.save()
            if archive_file.is_image:
                make_thumbnail(archive_file)
            return redirect("filarkiv_folder", pk=archive_file.folder_id)
    else:
        mappe = request.GET.get("mappe", "")
        initial_folder = Folder.objects.filter(pk=mappe).first() if mappe.isdigit() else None
        form = ArchiveFileForm(initial={"folder": initial_folder})
    return render(request, "filarkiv/upload_form.html", {"form": form})


def file_edit(request, pk):
    archive_file = get_object_or_404(ArchiveFile, pk=pk)
    form = ArchiveFileEditForm(request.POST or None, instance=archive_file)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("filarkiv_folder", pk=archive_file.folder_id)
    return render(request, "filarkiv/file_edit.html", {"form": form, "file": archive_file})


@require_POST
def delete_file(request, pk):
    archive_file = get_object_or_404(ArchiveFile, pk=pk)
    archive_file.delete_stored_files()
    archive_file.delete()
    return redirect("filarkiv_folder", pk=archive_file.folder_id)


def download_file(request, pk):
    archive_file = get_object_or_404(ArchiveFile, pk=pk)
    return FileResponse(
        archive_file.file.open("rb"),
        as_attachment=True,
        filename=archive_file.filename,
    )


def view_image(request, pk):
    archive_file = get_object_or_404(ArchiveFile, pk=pk)
    if not archive_file.is_image:
        raise Http404
    return _inline(archive_file.file, archive_file.content_type, archive_file.filename)


def thumbnail(request, pk):
    archive_file = get_object_or_404(ArchiveFile, pk=pk)
    if not archive_file.thumbnail:
        raise Http404
    return _inline(archive_file.thumbnail, "image/jpeg", "miniature.jpg")


def _inline(field_file, content_type, filename):
    response = FileResponse(field_file.open("rb"), content_type=content_type, filename=filename)
    response["Content-Security-Policy"] = INLINE_CSP
    # A record's file never changes, so the grid and the viewer can reuse it.
    response["Cache-Control"] = "private, max-age=86400"
    return response
