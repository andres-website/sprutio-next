# Тестовый WebDAV (Apache mod_dav). DirectoryIndex отключён: иначе Apache подменяет запросы к папке,
# где лежит index.html, на сам файл — PROPFIND/DELETE по такой папке ломаются в любом WebDAV-клиенте.
FROM bytemark/webdav:2.4
RUN sed -i 's/^\(\s*\)DirectoryIndex index.html/\1DirectoryIndex disabled/' /usr/local/apache2/conf/httpd.conf \
 && grep -q "DirectoryIndex disabled" /usr/local/apache2/conf/httpd.conf
